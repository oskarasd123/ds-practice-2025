import sys
import os
from google.protobuf import empty_pb2

# This set of lines are needed to import the gRPC stubs.
# The path of the stubs is relative to the current file, or absolute inside the container.
# Change these lines only if strictly needed.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
root_path = os.path.abspath(os.path.join(FILE, '../../..'))
sys.path.insert(0, root_path)
sys.path.append(os.path.join(root_path, 'utils/pb/fraud_detection'))
sys.path.append(os.path.join(root_path, 'utils/pb/transaction_verification'))
sys.path.append(os.path.join(root_path, 'utils/pb/suggestions'))
sys.path.append(os.path.join(root_path, 'utils/pb/orchestrator'))
import utils.pb.fraud_detection.fraud_detection_pb2 as fraud_detection
import utils.pb.fraud_detection.fraud_detection_pb2_grpc as fraud_detection_grpc

import utils.pb.transaction_verification.transaction_verification_pb2 as transaction_verification
import utils.pb.transaction_verification.transaction_verification_pb2_grpc as transaction_verification_grpc

import utils.pb.suggestions.suggestions_pb2 as suggestions
import utils.pb.suggestions.suggestions_pb2_grpc as suggestions_grpc

import utils.pb.orchestrator.orchestrator_pb2 as orchestrator
import utils.pb.orchestrator.orchestrator_pb2_grpc as orchestrator_grpc

import grpc
from concurrent import futures
import logging


logging.basicConfig(
    filename="/logs/transaction_logs.txt",
    filemode="a",
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# Create a class to define the server functions, derived from
# fraud_detection_pb2_grpc.TransactionVerificationService
class TransactionVerificationService(transaction_verification_grpc.transactionServiceServicer):
    def initOrder(self, request, context):
        return empty_pb2.Empty()
    def checkCard(self, request, context):
        return empty_pb2.Empty()
    def checkMoney(self, request, context):
        return empty_pb2.Empty()
    def startPayment(self, request, context):
        return empty_pb2.Empty()

def serve():
    # Create a gRPC server
    server = grpc.server(futures.ThreadPoolExecutor())
    transaction_verification_grpc.add_transactionServiceServicer_to_server(TransactionVerificationService(), server)
    # Listen on port 50052
    port = "50052"
    server.add_insecure_port("[::]:" + port)
    # Start the server
    server.start()
    logger.info("Server started. Listening on port 50052.")
    # Keep thread alive
    server.wait_for_termination()

if __name__ == '__main__':
    serve()