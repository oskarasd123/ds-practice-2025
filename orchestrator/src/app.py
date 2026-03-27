import sys
import os
import random
from threading import Thread

# This set of lines are needed to import the gRPC stubs.
# The path of the stubs is relative to the current file, or absolute inside the container.
# Change these lines only if strictly needed.
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


import logging

# Configure logging to file and console
logging.basicConfig(
    filename="/logs/orchestrator_logs.txt",
    filemode="a",
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


fraud_channel = grpc.insecure_channel('fraud_detection:50051')
verification_channel = grpc.insecure_channel('transaction_verification:50052')
suggestion_channel = grpc.insecure_channel("suggestions:50053")

fraud_stub = fraud_detection_grpc.FraudDetectionServiceStub(fraud_channel)
verification_stub = transaction_verification_grpc.transactionServiceStub(verification_channel)
suggestion_stub = suggestions_grpc.SuggestionsServiceStub(suggestion_channel)





def orchestrator_checkout_flow(order_id, order_data):
    fraud_stub.InitOrder(order_id, order_data)
    verification_stub.InitOrder(order_id, order_data)
    suggestion_stub.InitOrder(order_id, order_data)
    
    fails = []

    def fraud_start():
        fraud_stub.bookCheck(order_id)
    
    def verification_start():
        verification_stub.checkCard(order_id)
    
    fraud_thread = Thread(target=fraud_start)
    verification_thread = Thread(target=verification_start)
    fraud_thread.start()
    verification_thread.start()
            


# Import Flask.
# Flask is a web framework for Python.
# It allows you to build a web application quickly.
# For more information, see https://flask.palletsprojects.com/en/latest/
from flask import Flask, request, jsonify
from flask_cors import CORS
import json

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
    order_id = int.from_bytes(os.urandom(8)) # equivalent to random.randint(0, 2**63 - 1) a random 64 bit unsigned integer
    # Print request object data

    quantity = sum([item["quantity"] for item in request_data["items"]])

    order_data = [
        order_id, request_data["creditCard"]["number"], quantity,
    ]


    # Convert the gRPC response to a dictionary
    suggested_books_dicts = []
    #for book in suggested_books:
    #    suggested_books_dicts.append({
    #        'bookId': book.bookId,
    #        'title': book.title,
    #        'author': book.author
    #    })

    suggested_books_dicts = [{
        "bookId" : "8942786189",
        "titile" : "1999",
        "author" : "Timmy"
    }]

    is_fraud = False


    # Dummy response following the provided YAML specification for the bookstore
    order_status_response = {
        'orderId': str(order_id),
        'status': ('Order Rejected' if is_fraud else 'Order Approved'),
        'suggestedBooks': suggested_books_dicts if not is_fraud else [],
    }

    return jsonify(order_status_response)

suggestion_channel.close()
verification_channel.close()
fraud_channel.close()

if __name__ == '__main__':
    # Run the app in debug mode to enable hot reloading.
    # This is useful for development.
    # The default port is 5000.
    app.run(host='0.0.0.0')