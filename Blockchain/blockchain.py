
from web3 import Web3
import json
from pathlib import Path

# Connect to local Ganache
RPC_URL = "http://127.0.0.1:7545"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Load contract details
contract_info_path = Path(__file__).resolve().parent / "contract_info.json"

with open(contract_info_path, "r", encoding="utf-8") as file:
    contract_info = json.load(file)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(contract_info["address"]),
    abi=contract_info["abi"]
)


def check_blockchain():
    if not w3.is_connected():
        raise ConnectionError(
            "Ganache is not running at http://127.0.0.1:7545."
        )


def get_account():
    check_blockchain()
    accounts = w3.eth.accounts

    if not accounts:
        raise RuntimeError("No accounts found in Ganache.")

    return accounts[0]


def send_transaction(function_call):
    """Send a transaction using the first Ganache account."""
    account = get_account()

    tx_hash = function_call.transact({"from": account})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        raise RuntimeError("Blockchain transaction failed.")

    return tx_hash.hex()


def register_product(serial_no, manufacturer):
    return send_transaction(
        contract.functions.registerProduct(serial_no, manufacturer)
    )


def assign_seller(serial_no, seller):
    return send_transaction(
        contract.functions.assignSeller(serial_no, seller)
    )


def assign_consumer(serial_no, consumer):
    return send_transaction(
        contract.functions.assignConsumer(serial_no, consumer)
    )


def verify_product(serial_no):
    check_blockchain()

    manufacturer, seller, consumer, exists = (
        contract.functions.verifyProduct(serial_no).call()
    )

    return {
        "manufacturer": manufacturer,
        "seller": seller,
        "consumer": consumer,
        "exists": exists
    }
