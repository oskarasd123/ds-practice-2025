import sys
import os
import grpc
from concurrent import futures

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
root_path = os.path.abspath(os.path.join(FILE, '../../..'))
sys.path.insert(0, os.path.join(root_path, 'utils/pb/payment'))

import payment_pb2
import payment_pb2_grpc

PAYMENT_PORT = os.getenv("PAYMENT_PORT")
if PAYMENT_PORT is None:
    raise RuntimeError("PAYMENT_PORT environment variable is required!")


class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    def __init__(self):
        self.prepared = False

    def Prepare(self, request, context):
        self.prepared = True
        return payment_pb2.PrepareResponse(ready=True)

    def Commit(self, request, context):
        if self.prepared:
            print(f"Payment committed for order {request.order_id}")
            self.prepared = False
        return payment_pb2.CommitResponse(success=True)

    def Abort(self, request, context):
        self.prepared = False
        print(f"Payment aborted for order {request.order_id}")
        return payment_pb2.AbortResponse(aborted=True)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    payment_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentService(), server)
    server.add_insecure_port(f"[::]:{PAYMENT_PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()