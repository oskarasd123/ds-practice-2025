import sys
import os
import threading
import grpc
from concurrent import futures
import logging
from google.protobuf import empty_pb2
import time
from BigBookAPI import book_script


# This set of lines are needed to import the gRPC stubs.
# The path of the stubs is relative to the current file, or absolute inside the container.
# Change these lines only if strictly needed.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")

suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)
import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc

orchestrator_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/orchestrator'))
sys.path.insert(0, orchestrator_grpc_path)
import orchestrator_pb2 as orchestrator
import orchestrator_pb2_grpc as orchestrator_grpc

logging.basicConfig(
    filename="/logs/suggestions_logs.txt",
    filemode="a",
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
    # handlers=[
    #     logging.FileHandler("/logs/suggestions_logs.txt"),
    #     logging.StreamHandler()  # ← also print to docker logs
    # ]
)

logger = logging.getLogger(__name__)

#TODO update to make it dynamic
ORCH_PORT = 5050
# ORCH_PORT = os.getenv("ORCH_PORT")
if ORCH_PORT is None:
    raise RuntimeError("ORCH_PORT environment variable is required!")

port = os.getenv("SUGGESTIONS_PORT")
if port is None:
    raise RuntimeError("SUGGESTIONS_PORT environment variable is required!")

api_key = os.getenv("API_KEY")
if api_key is None:
    raise RuntimeError("API_KEY environment variable is required!")

SVC_IDX   = 2       # TV=0, FD=1, Suggestions=2
TOTAL_SVCS = 3

orch_channel = grpc.insecure_channel(f'orchestrator:{ORCH_PORT}')
orch_stub    = orchestrator_grpc.OrchestratorServiceStub(orch_channel)

orders = {}           # order_id -> {"vc": [0, 0, 0]}
orders_lock = threading.Lock()


def merge_and_increment(local_vc: list, incoming_vc: list) -> list:
    for i in range(TOTAL_SVCS):
        local_vc[i] = max(local_vc[i], incoming_vc[i])
    local_vc[SVC_IDX] += 1
    return local_vc


def proto_to_list(vc_proto) -> list:
    vals = list(vc_proto.values)
    return vals if vals else [0] * TOTAL_SVCS

# Create a class to define the server functions, derived from
# fraud_detection_pb2_grpc.HelloServiceServicer
class SuggestionsService(suggestions_grpc.SuggestionsServiceServicer):
    def initOrder(self, request, context):
        with orders_lock:
            orders[request.order_id] = {"vc": [0] * TOTAL_SVCS}
        logger.info(f"[{request.order_id}] initOrder vc={orders[request.order_id]['vc']}")
        return empty_pb2.Empty()

    # event (f)
    def getSuggestions(self, request, context):
        # time.sleep(1)

        with orders_lock:
            entry = orders.get(request.order_id)
            incoming = proto_to_list(request.clock)
            merge_and_increment(entry["vc"], incoming)
            clock_snap = list(entry["vc"])
        if entry is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Order {request.order_id} not found")

        logger.info(f"[{request.order_id}] (f) getSuggestions vc={clock_snap}")

        books = []
        # for book in request.ordered_books:
        #     logger.info("Fetching suggestions for: %s", book)
        #     books = books + book_script.get_book_suggestions(book, api_key=api_key)

        # in case API service doesn't work
        books = [
            {'bookId': '123', 'title': 'The Best Book', 'author': 'Author 1'},
            {'bookId': '456', 'title': 'The Second Best Book', 'author': 'Author 2'}
        ]

        # if len(books) > 0:
        #     for b in books:
        #         book = response.suggested_books.add()  # Use .add() to create a new Book
        #         book.bookId = str(b['bookId'])
        #         book.title = b['title']
        #         book.author = b['author']

        logger.info(f"[{request.order_id}] (f) returning {len(books)} suggestions")
        orch_stub.suggestionsDone(orchestrator.suggestionsDoneRequest(
            order_id=request.order_id,
            suggestions=[b['title'] for b in books], # TODO update proto file so we can also push authors to fronend
            clock=orchestrator.VectorClock(values=clock_snap),
        ))

        return empty_pb2.Empty()

    def clearOrder(self, request, context):
        final_vc = list(request.final_clock.values)
        with orders_lock:
            entry = orders.get(request.order_id)
            if entry is None:
                logger.warning(f"[{request.order_id}] clearOrder: order not found")
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
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add HelloService
    suggestions_grpc.add_SuggestionsServiceServicer_to_server(SuggestionsService(), server)

    # Listen on port 50053
    server.add_insecure_port("[::]:" + port)

    # Start the server
    server.start()
    # print(f"Server started. Listening on port {port}.")
    logger.info(f"Server started. Listening on port {port}.")

    # Keep thread alive
    server.wait_for_termination()

if __name__ == '__main__':
    serve()