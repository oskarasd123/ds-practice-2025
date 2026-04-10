import sys
import os
import threading

import grpc
from concurrent import futures
import logging

from google.protobuf import empty_pb2

# This set of lines are needed to import the gRPC stubs.
# The path of the stubs is relative to the current file, or absolute inside the container.
# Change these lines only if strictly needed.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")

transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_verification_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc

orchestrator_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/orchestrator'))
sys.path.insert(0, orchestrator_grpc_path)
import orchestrator_pb2 as orchestrator
import orchestrator_pb2_grpc as orchestrator_grpc

logging.basicConfig(
    filename="/logs/transaction_logs.txt",
    filemode="a",
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

#TODO update to make it dynamic
ORCH_PORT = 5050
# ORCH_PORT = os.getenv("ORCH_PORT")
if ORCH_PORT is None:
    raise RuntimeError("ORCH_PORT environment variable is required!")

PORT = os.getenv("TRANSACTION_PORT")
if PORT is None:
    raise RuntimeError("TRANSACTION_PORT environment variable is required!")

# TODO get this from environment?
SVC_IDX    = 0   # TV=0, FD=1, Suggestions=2
TOTAL_SVCS = 3


orch_channel = grpc.insecure_channel(f'orchestrator:{ORCH_PORT}')
orch_stub    = orchestrator_grpc.OrchestratorServiceStub(orch_channel)

orders = {}          # order_id -> {"data": OrderData, "vc": [0,0,0]}
orders_lock = threading.Lock()

def merge_and_increment(local_vc: list, incoming_vc: list) -> list:
    for i in range(TOTAL_SVCS):
        local_vc[i] = max(local_vc[i], incoming_vc[i])
    local_vc[SVC_IDX] += 1 # increment this service's slot
    return local_vc

def proto_to_list(vc_proto) -> list:
    return list(vc_proto.values) or [0] * TOTAL_SVCS

def list_to_proto(vc_list: list):
    vc = transaction_verification.VectorClock()
    vc.values.extend(vc_list)
    return vc

def callback(order_id: int, event_name: str, vc: list,
             failed=False, error_msg="", is_fraud=False):
    """Calls back orchestrator.eventDone."""
    orch_stub.eventDone(orchestrator.EventDoneRequest(
        order_id=order_id, event_name=event_name,
        clock=orchestrator.VectorClock(values=vc),
        failed=failed, error_msg=error_msg, is_fraud=is_fraud,
    ))

# Create a class to define the server functions, derived from
# fraud_detection_pb2_grpc.TransactionVerificationService
class TransactionVerificationService(transaction_verification_grpc.transactionServiceServicer):
    def initOrder(self, request, context):
        print(f"initOrder received: {request}")

        with orders_lock:
            orders[request.order_id] = {
                "data": request.data,
                "vc":   [0] * TOTAL_SVCS,
            }
        logger.info(f"[{request.order_id}] initOrder vc={orders[request.order_id]['vc']}")
        return empty_pb2.Empty()

    # ── Event (a): items not empty ──
    def checkItems(self, request, context):
        print("CHECK ITEMS - A \n")
        with orders_lock:
            entry = orders.get(request.order_id)
        incoming = proto_to_list(request.clock)
        merge_and_increment(entry["vc"], incoming)
        logger.info(f"[{request.order_id}] (a) checkItems vc={entry['vc']}")

        failed = len(entry["data"].items) == 0
        print("EVENT A failed ", failed)
        callback(request.order_id, "a", list(entry["vc"]),
                 failed=failed, error_msg="Items list is empty" if failed else "")
        return empty_pb2.Empty()

    # ── Event (b): user data filled ──
    def checkUserData(self, request, context):
        print("checkUserData - B \n")
        with orders_lock:
            entry = orders.get(request.order_id)
        incoming = proto_to_list(request.clock)
        merge_and_increment(entry["vc"], incoming)
        logger.info(f"[{request.order_id}] (b) checkUserData vc={entry['vc']}")

        data   = entry["data"]
        failed = not (data.user_name and data.user_contact) # currently we only get card nr and order amount
        print("EVENT b failed ", failed)
        callback(request.order_id, "b", list(entry["vc"]),
                 failed=failed, error_msg="Missing user fields" if failed else "")
        return empty_pb2.Empty()

    # ── Event (c): card format ──
    def checkCard(self, request, context):
        print("checkCard - C\n")
        with orders_lock:
            entry = orders.get(request.order_id)
        incoming = proto_to_list(request.clock)
        merge_and_increment(entry["vc"], incoming)
        logger.info(f"[{request.order_id}] (c) checkCard vc={entry['vc']}")

        card   = entry["data"].card_nr
        failed = not (card.isdigit() and len(card) == 16)
        print("EVENT C failed ", failed)
        callback(request.order_id, "c", list(entry["vc"]),
                 failed=failed, error_msg="Invalid card format" if failed else "")
        return empty_pb2.Empty()

    # ── Bonus: clear order data ──
    def clearOrder(self, request, context):
        final_vc = list(request.final_clock.values)
        with orders_lock:
            entry = orders.get(request.order_id)
            if entry is None:
                logger.warning(f"[{request.order_id}] clearOrder: not found")
                return empty_pb2.Empty()
            local_vc = entry["vc"]

        # Validate: local_vc <= final_vc componentwise
        if all(local_vc[i] <= final_vc[i] for i in range(TOTAL_SVCS)):
            with orders_lock:
                orders.pop(request.order_id, None)
            logger.info(f"[{request.order_id}] clearOrder OK local={local_vc} final={final_vc}")
        else:
            logger.error(f"[{request.order_id}] clearOrder CLOCK ERROR local={local_vc} > final={final_vc}")
        return empty_pb2.Empty()

def serve():
    # Create a gRPC server
    server = grpc.server(futures.ThreadPoolExecutor())
    transaction_verification_grpc.add_transactionServiceServicer_to_server(TransactionVerificationService(), server)
    
    # Listen on port 50052
    server.add_insecure_port("[::]:" + PORT)

    # Start the server
    server.start()
    logger.info(f"Server started. Listening on port {PORT}.")

    # Keep thread alive
    server.wait_for_termination()

if __name__ == '__main__':
    serve()