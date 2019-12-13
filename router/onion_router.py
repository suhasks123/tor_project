from connection.skt import Skt
from router.circuit import Circuit
import threading

class OnionRouter:

    def __init__(self, node=None, is_exit_node=True):
        self.node = node
        self.skt = Skt(node.host, node.port)
        self.is_exit_node = is_exit_node
        self.circuits_list = []
        self.circuits_threads = []
        self.routing_table = {}

    def get_rand_circ_id(self) -> int:
        return 1

    def listen(self):
        l = self.skt.server_listen()
        if l != 0:
            print("Error listening")
            exit(0)
        return -1

    def accept(self):
        a = self.skt.server_accept()
        if a != 0:
            print("Error accepting connection")
            exit(0)
        cktid = self.get_rand_circ_id()
        ckt = Circuit(cktid, self.node, self.skt.conn)
        self.circuits_list.append(ckt)

        circuit_th = threading.Thread(target=ckt.main(), args=())
        self.circuits_threads.append(circuit_th)
        circuit_th.start()

        return -1
