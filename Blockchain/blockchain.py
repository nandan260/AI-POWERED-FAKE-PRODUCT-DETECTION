from web3 import Web3
import json

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

with open("Blockchain/contract_info.json", "r") as f:
    contract_info = json.load(f)

contract = w3.eth.contract(
    address=contract_info["address"],
    abi=contract_info["abi"]
)


account = w3.eth.accounts[0]
def register_product(serial_no, manufacturer):

    tx = contract.functions.registerProduct(
        serial_no,
        manufacturer
    ).transact({
        "from": account
    })

    w3.eth.wait_for_transaction_receipt(tx)

    return tx.hex()


def assign_seller(serial_no, seller):

    tx = contract.functions.assignSeller(
        serial_no,
        seller
    ).transact({
        "from": account
    })

    w3.eth.wait_for_transaction_receipt(tx)

    return tx.hex()

def assign_consumer(serial_no, consumer):

    tx = contract.functions.assignConsumer(
        serial_no,
        consumer
    ).transact({
        "from": account
    })

    w3.eth.wait_for_transaction_receipt(tx)

    return tx.hex()

def verify_product(serial_no):

    manufacturer, seller, consumer, exists = contract.functions.verifyProduct(
        serial_no
    ).call()

    return {
        "manufacturer": manufacturer,
        "seller": seller,
        "consumer": consumer,
        "exists": exists
    }