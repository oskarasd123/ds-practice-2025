import sys
import os

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
root_path = os.path.abspath(os.path.join(FILE, '../../..'))
sys.path.insert(0, root_path)
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
    filename="/logs/fraud_detection_logs.txt",
    filemode="a",
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Create a class to define the server functions, derived from
# fraud_detection_pb2_grpc.HelloServiceServicer
class FraudDetectionService(fraud_detection_grpc.FraudDetectionService):
    
    def bookCheck(self, request, context):
        pass

def serve():
    # Create a gRPC server
    server = grpc.server(futures.ThreadPoolExecutor())
    # Add HelloService
    fraud_detection_grpc.add_FraudDetectionServiceServicer_to_server(FraudDetectionService(), server)
    # Listen on port 50051
    port = "50051"
    server.add_insecure_port("[::]:" + port)
    # Start the server
    server.start()
    logger.info("Server started. Listening on port 50051.")
    # Keep thread alive
    server.wait_for_termination()

if __name__ == '__main__':
    serve()