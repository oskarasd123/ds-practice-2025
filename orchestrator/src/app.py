import sys
import os
import random
import threading
from threading import Thread, Event
import grpc

import logging
from concurrent.futures import ThreadPoolExecutor
# import time

# Import Flask.
# Flask is a web framework for Python.
# It allows you to build a web application quickly.
# For more information, see https://flask.palletsprojects.com/en/latest/
from flask import Flask, request, jsonify
from flask_cors import CORS
import json

from google.protobuf import empty_pb2

# This set of lines are needed to import the gRPC stubs.
# The path of the stubs is relative to the current file, or absolute inside the container.
# Change these lines only if strictly needed.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)
import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_verification_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc

suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)
import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc

orchestrator_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/orchestrator'))
sys.path.insert(0, orchestrator_grpc_path)
import orchestrator_pb2 as orchestrator
import orchestrator_pb2_grpc as orchestrator_grpc

# Configure logging to file and console
logging.basicConfig(
    filename="/logs/orchestrator_logs.txt",
    filemode="a",
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
)

# Set up logging configuration for the console only
# logging.basicConfig(
#     format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
#     level=logging.INFO,
#     handlers=[logging.StreamHandler()]
# )

logger = logging.getLogger(__name__)
debug_flag = os.getenv("DEBUG_FLAG", "False")

#TODO update to make it dynamic
ORCH_PORT = 5050
# ORCH_PORT = os.getenv("ORCH_PORT")
if ORCH_PORT is None:
    raise RuntimeError("ORCH_PORT environment variable is required!")

FRAUD_DETECTION_PORT = os.getenv("FRAUD_DETECTION_PORT")
if FRAUD_DETECTION_PORT is None:
    raise RuntimeError("FRAUD_DETECTION_PORT environment variable is required!")

TRANSACTION_PORT = os.getenv("TRANSACTION_PORT")
if TRANSACTION_PORT is None:
    raise RuntimeError("TRANSACTION_PORT environment variable is required!")

SUGGESTIONS_PORT = os.getenv("SUGGESTIONS_PORT")
if SUGGESTIONS_PORT is None:
    raise RuntimeError("SUGGESTIONS_PORT environment variable is required!")

SVC_IDX    = {"tv": 0, "fd": 1, "sg": 2}
TOTAL_SVCS = 3

fraud_channel = grpc.insecure_channel(f'fraud_detection:{FRAUD_DETECTION_PORT}')
verification_channel = grpc.insecure_channel(f'transaction_verification:{TRANSACTION_PORT}')
suggestion_channel = grpc.insecure_channel(f"suggestions:{SUGGESTIONS_PORT}")

fraud_stub = fraud_detection_grpc.FraudDetectionServiceStub(fraud_channel)
verification_stub = transaction_verification_grpc.transactionServiceStub(verification_channel)
suggestion_stub = suggestions_grpc.SuggestionsServiceStub(suggestion_channel)

# ── Per-order coordination state ──
class OrderFlow:
    def __init__(self):
        self.lock        = threading.Lock()
        self.done        = Event()          # set when flow finishes
        self.failed      = False
        self.error_msg   = ""
        self.is_fraud    = False
        self.suggestions = []
        self.final_clock = [0] * TOTAL_SVCS
        # gate for event (e): needs both (c) and (d) done
        self.c_done      = False
        self.d_done      = False
        self.c_clock     = [0] * TOTAL_SVCS
        self.d_clock     = [0] * TOTAL_SVCS

flows: dict[int, OrderFlow] = {}


def merge(a: list, b: list) -> list:
    return [max(a[i], b[i]) for i in range(TOTAL_SVCS)]

class OrchestratorServicer(orchestrator_grpc.OrchestratorServiceServicer):

    def eventDone(self, request, context):
        order_id   = request.order_id
        event_name = request.event_name
        clock      = list(request.clock.values) or [0] * TOTAL_SVCS
        flow       = flows.get(order_id)

        logger.info(f"[{order_id}] eventDone event={event_name} clock={clock} failed={request.failed}")
        print(f"[{order_id}] eventDone event={event_name} clock={clock} failed={request.failed}", flush=True)

        if not flow:
            return empty_pb2.Empty()

        # Propagate failure immediately
        if request.failed:
            with flow.lock:
                if not flow.done.is_set():
                    flow.failed      = True
                    flow.error_msg   = request.error_msg
                    flow.final_clock = clock
                    flow.done.set()
            return empty_pb2.Empty()

        if event_name == "a":
            def trigger_c():
                try:
                    print(f"[{order_id}] triggering (c) checkCard", flush=True)
                    verification_stub.checkCard(
                        transaction_verification.EventRequest(
                            order_id=order_id,
                            clock=transaction_verification.VectorClock(values=clock)))
                except Exception as e:
                    print(f"[{order_id}] trigger_c FAILED: {e}", flush=True)
                    logger.error(f"[{order_id}] trigger_c FAILED: {e}")
                    with flow.lock:
                        if not flow.done.is_set():
                            flow.failed      = True
                            flow.error_msg   = str(e)
                            flow.final_clock = clock
                            flow.done.set()
            Thread(target=trigger_c, daemon=True).start()

        elif event_name == "b":
            def trigger_d():
                try:
                    print(f"[{order_id}] triggering (d) userCheck", flush=True)
                    fraud_stub.userCheck(
                        fraud_detection.EventRequest(
                            order_id=order_id,
                            clock=fraud_detection.VectorClock(values=clock)))
                except Exception as e:
                    print(f"[{order_id}] trigger_d FAILED: {e}", flush=True)
                    logger.error(f"[{order_id}] trigger_d FAILED: {e}")
                    with flow.lock:
                        if not flow.done.is_set():
                            flow.failed      = True
                            flow.error_msg   = str(e)
                            flow.final_clock = clock
                            flow.done.set()
            Thread(target=trigger_d, daemon=True).start()

        elif event_name in ("c", "d"):
            with flow.lock:
                if event_name == "c":
                    flow.c_done  = True
                    flow.c_clock = clock
                else:
                    flow.d_done  = True
                    flow.d_clock = clock

                fire_e  = flow.c_done and flow.d_done
                merged  = merge(flow.c_clock, flow.d_clock) if fire_e else None

            if fire_e:
                def trigger_e():
                    try:
                        print(f"[{order_id}] triggering (e) cardCheck clock={merged}", flush=True)
                        fraud_stub.cardCheck(
                            fraud_detection.EventRequest(
                                order_id=order_id,
                                clock=fraud_detection.VectorClock(values=merged)))
                    except Exception as e:
                        print(f"[{order_id}] trigger_e FAILED: {e}", flush=True)
                        logger.error(f"[{order_id}] trigger_e FAILED: {e}")
                        with flow.lock:
                            if not flow.done.is_set():
                                flow.failed      = True
                                flow.error_msg   = str(e)
                                flow.final_clock = merged
                                flow.done.set()
                Thread(target=trigger_e, daemon=True).start()
            else:
                print(f"[{order_id}] event {event_name} done, waiting for the other of (c)/(d)", flush=True)

        elif event_name == "e":
            def trigger_f():
                try:
                    print(f"[{order_id}] triggering (f) getSuggestions", flush=True)
                    suggestion_stub.getSuggestions(
                        suggestions.getSuggestionsRequest(
                            order_id=order_id,
                            clock=suggestions.VectorClock(values=clock)))
                except Exception as e:
                    print(f"[{order_id}] trigger_f FAILED: {e}", flush=True)
                    logger.error(f"[{order_id}] trigger_f FAILED: {e}")
                    with flow.lock:
                        if not flow.done.is_set():
                            flow.failed      = True
                            flow.error_msg   = str(e)
                            flow.final_clock = clock
                            flow.done.set()
            Thread(target=trigger_f, daemon=True).start()

        else:
            logger.warning(f"[{order_id}] unknown event_name={event_name}")

        return empty_pb2.Empty()

    def suggestionsDone(self, request, context):
        order_id = request.order_id
        clock    = list(request.clock.values) or [0] * TOTAL_SVCS
        flow     = flows.get(order_id)
        if flow and not flow.done.is_set():
            flow.suggestions = list(request.suggestions)
            flow.final_clock = clock
            flow.done.set()
        logger.info(f"[{order_id}] suggestionsDone clock={clock}")
        return empty_pb2.Empty()


def broadcast_clear(order_id: int, final_vc: list):
    """Bonus: tell all services to clear order data."""
    def clear(stub, proto_module):
        try:
            stub.clearOrder(proto_module.ClearRequest(
                order_id=order_id,
                final_clock=proto_module.VectorClock(values=final_vc)))
        except Exception as e:
            logger.error(f"[{order_id}] clearOrder failed: {e}")

    threads = [
        Thread(target=clear, args=(verification_stub, transaction_verification)),
        Thread(target=clear, args=(fraud_stub, fraud_detection)),
        Thread(target=clear, args=(suggestion_stub, suggestions)),
    ]
    for t in threads: t.start()
    # Fire-and-forget — don't block the response


def orchestrator_checkout_flow(order_id: int, request_data: dict):
    flow = OrderFlow()
    flows[order_id] = flow


    order_data = transaction_verification.OrderData(
        card_nr=request_data["creditCard"]["number"],
        order_amount=float(sum(i["quantity"] for i in request_data["items"])),
        items=[i["name"] for i in request_data["items"]],
        user_name=request_data.get("user", {}).get("name", ""),
        user_contact=request_data.get("user", {}).get("contact", ""),
    )

    # Init all services in parallel
    def init_tv():
        verification_stub.initOrder(
            transaction_verification.InitRequest(order_id=order_id, data=order_data)
        )
    def init_fd():
        fraud_stub.initOrder(
            fraud_detection.InitRequest(
                order_id=order_id,
                data=fraud_detection.OrderData(
                    card_nr=order_data.card_nr,
                    order_amount=order_data.order_amount
                    )
                )
            )
    def init_sg():
        suggestion_stub.initOrder(
            suggestions.InitRequest(order_id=order_id)
        )

    init_threads = [Thread(target=f) for f in (init_tv, init_fd, init_sg)]
    for t in init_threads: t.start()
    for t in init_threads: t.join()

    # Kick off (a) and (b) in parallel — both call back via eventDone
    init_clock = [0] * TOTAL_SVCS
    Thread(target=lambda: verification_stub.checkItems(
        transaction_verification.EventRequest(order_id=order_id,
                            clock=transaction_verification.VectorClock(values=init_clock)))).start()

    Thread(target=lambda: verification_stub.checkUserData(
        transaction_verification.EventRequest(order_id=order_id,
                            clock=transaction_verification.VectorClock(values=init_clock)))).start()

    # Block until the flow completes (success or first failure)
    flow.done.wait(timeout=30)
    final_vc = flow.final_clock

    # Broadcast clear (bonus) — fire and forget
    # Thread(target=broadcast_clear, args=(order_id, final_vc), daemon=True).start()
    # flows.pop(order_id, None)

    return flow.failed, flow.error_msg, flow.is_fraud, flow.suggestions



def serve_grpc():
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    orchestrator_grpc.add_OrchestratorServiceServicer_to_server(OrchestratorServicer(), server)
    server.add_insecure_port(f'[::]:{ORCH_PORT}')
    server.start()
    logger.info(f"Orchestrator gRPC listening on 0:0:0:0:{ORCH_PORT}")
    server.wait_for_termination()

# Create a simple Flask app.
app = Flask(__name__)
# Enable CORS for the app.
CORS(app, resources={r'/*': {'origins': '*'}})

# Define a GET endpoint.
@app.route('/', methods=['GET'])
def index():
    """
    Responds with 'Hello, [name]' when a GET request is made to '/' endpoint.
    """
    # Return the response.
    return "hello orchestrator"

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Responds with a JSON object containing the order ID, status, and suggested books.
    """
    # Get request object data to json
    request_data = json.loads(request.data)
    order_id = int.from_bytes(os.urandom(4)) # equivalent to random.randint(0, 2**63 - 1) a random 64 bit unsigned integer
    # Print request object data

    # quantity = sum([item["quantity"] for item in request_data["items"]])
    failed, error_msg, is_fraud, suggested_books = orchestrator_checkout_flow(order_id, request_data)

    if failed:
        return jsonify({'orderId': str(order_id), 'status': 'Order Rejected',
                        'suggestedBooks': [], 'reason': error_msg})


    return jsonify({
        'orderId': str(order_id),
        'status': 'Order Rejected' if is_fraud else 'Order Approved',
        'suggestedBooks': [{'title': b} for b in suggested_books] if not is_fraud else [],
    })
    # order_data = [
    #     order_id, request_data["creditCard"]["number"], quantity,
    # ]


    # Convert the gRPC response to a dictionary
    suggested_books_dicts = []
#     for book in suggested_books:
#        suggested_books_dicts.append({
#            'bookId': book.bookId,
#            'title': book.title,
#            'author': book.author
#        })

    # suggested_books_dicts = [{
    #     "bookId" : "8942786189",
    #     "titile" : "1999",
    #     "author" : "Timmy"
    # }]

    # is_fraud = False


    # Dummy response following the provided YAML specification for the bookstore
    order_status_response = {
        'orderId': str(order_id),
        'status': ('Order Rejected' if is_fraud else 'Order Approved'),
        'suggestedBooks': suggested_books_dicts if not is_fraud else [],
    }

    logger.info(f"Order {order_id} processed with status: {order_status_response['status']}")
#     logger.info(f"Checkout completed in {time.time() - start_time:.2f} seconds")
    return jsonify(order_status_response)

if __name__ == '__main__':

    # Run the app in debug mode to enable hot reloading.
    # This is useful for development.
    # The default port is 5000.
    grpc_thread = Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()
    # not sure what is this reloader, but looks like we need it for threads / vector clocks to work properly
    app.run(host='0.0.0.0', debug=debug_flag, use_reloader=False)