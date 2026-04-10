import sys
import os
import threading
from concurrent import futures
from google.protobuf import empty_pb2

import grpc
import logging

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")

fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)
import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

# transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
# sys.path.insert(0, transaction_verification_grpc_path)
# import transaction_verification_pb2 as transaction_verification
# import transaction_verification_pb2_grpc as transaction_verification_grpc

# suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
# sys.path.insert(0, suggestions_grpc_path)
# import suggestions_pb2 as suggestions
# import suggestions_pb2_grpc as suggestions_grpc

orchestrator_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/orchestrator'))
sys.path.insert(0, orchestrator_grpc_path)
import orchestrator_pb2 as orchestrator
import orchestrator_pb2_grpc as orchestrator_grpc

logging.basicConfig(
    filename="/logs/fraud_detection_logs.txt",
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

PORT = os.getenv("FRAUD_DETECTION_PORT")
if PORT is None:
    raise RuntimeError("FRAUD_DETECTION_PORT environment variable is required!")

# TODO get this from environment?
SVC_IDX   = 1  # TV=0, FD=1, Suggestions=2
TOTAL_SVCS = 3

orch_channel = grpc.insecure_channel(f'orchestrator:{ORCH_PORT}')
orch_stub    = orchestrator_grpc.OrchestratorServiceStub(orch_channel)

orders = {}
orders_lock = threading.Lock()


def merge_and_increment(local_vc, incoming_vc):
    for i in range(TOTAL_SVCS):
        local_vc[i] = max(local_vc[i], incoming_vc[i])
    local_vc[SVC_IDX] += 1
    return local_vc


def proto_to_list(vc_proto):
    return list(vc_proto.values) or [0] * TOTAL_SVCS

def callback(order_id, event_name, vc, failed=False, error_msg="", is_fraud=False):
    orch_stub.eventDone(orchestrator.EventDoneRequest(
        order_id=order_id, event_name=event_name,
        clock=orchestrator.VectorClock(values=vc),
        failed=failed, error_msg=error_msg, is_fraud=is_fraud,
    ))

# Create a class to define the server functions, derived from
# fraud_detection_pb2_grpc.HelloServiceServicer
class FraudDetectionService(fraud_detection_grpc.FraudDetectionService):
    def initOrder(self, request, context):
        with orders_lock:
            orders[request.order_id] = {
                "data": request.data,
                "vc":   [0] * TOTAL_SVCS,
            }

        logger.info(f"[{request.order_id}] initOrder vc={orders[request.order_id]['vc']}")
        return empty_pb2.Empty()

    # ── Event (d): user fraud check ──
    def userCheck(self, request, context):
        print("userCheck - D\n")
        with orders_lock:
            entry = orders.get(request.order_id)
        incoming = proto_to_list(request.clock)
        merge_and_increment(entry["vc"], incoming)
        logger.info(f"[{request.order_id}] (d) userCheck vc={entry['vc']}")

        print("EVENT D failed: false",)
        # Dummy: always passes
        callback(request.order_id, "d", list(entry["vc"]))
        return empty_pb2.Empty()

    # ── Event (e): card fraud check ──
    def cardCheck(self, request, context):
        print("cardCheck - E\n")
        with orders_lock:
            entry = orders.get(request.order_id)
        incoming = proto_to_list(request.clock)
        merge_and_increment(entry["vc"], incoming)
        logger.info(f"[{request.order_id}] (e) cardCheck vc={entry['vc']}")

        card     = entry["data"].card_nr
        is_fraud = not (card.isdigit() and len(card) == 16)
        print("EVENT e failed ", is_fraud)
        callback(request.order_id, "e", list(entry["vc"]), is_fraud=is_fraud)

        return empty_pb2.Empty()

    def clearOrder(self, request, context):
        final_vc = list(request.final_clock.values)

        with orders_lock:
            entry = orders.get(request.order_id)
            if entry is None:
                return empty_pb2.Empty()
            local_vc = entry["vc"]

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

    # Add HelloService
    fraud_detection_grpc.add_FraudDetectionServiceServicer_to_server(FraudDetectionService(), server)

    # Listen on port 50051
    server.add_insecure_port("[::]:" + PORT)

    # Start the server
    server.start()
    logger.info(f"Server started. Listening on port {PORT}.")

    # Keep thread alive
    server.wait_for_termination()

if __name__ == '__main__':
    serve()