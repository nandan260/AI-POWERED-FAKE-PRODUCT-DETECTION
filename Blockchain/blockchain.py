
from web3 import Web3
import json
import os
from pathlib import Path

# Use Ganache locally, or a remote RPC URL configured on Render.
rpc_url = os.environ.get(
    "BLOCKCHAIN_RPC_URL",
    "http://127.0.0.1:7545"
)

w3 = Web3(Web3.HTTPProvider(rpc_url))

# Load the deployed contract information.
contract_info_path = Path(__file__).resolve().parent / "contract_info.json"

with open(contract_info_path, "r") as f:
    contract_info = json.load(f)

contract = w3.eth.contract(
    address=contract_info["address"],
    abi=contract_info["abi"]
)


def check_blockchain():
    """Check the blockchain only when a blockchain function is called."""
    if not w3.is_connected():
        raise ConnectionError(
            "Blockchain is unavailable. Check the RPC URL and network."
        )


def get_account():
    """Get an account only when a transaction is needed."""
    check_blockchain()

    accounts = w3.eth.accounts

    if not accounts:
        raise RuntimeError("No blockchain accounts are available.")

    return accounts[0]


def register_product(serial_no, manufacturer):
    account = get_account()

    tx = contract.functions.registerProduct(
        serial_no,
        manufacturer
    ).transact({
        "from": account
    })

    w3.eth.wait_for_transaction_receipt(tx)

    return tx.hex()


def assign_seller(serial_no, seller):
    account = get_account()

    tx = contract.functions.assignSeller(
        serial_no,
        seller
    ).transact({
        "from": account
    })

    w3.eth.wait_for_transaction_receipt(tx)

    return tx.hex()


def assign_consumer(serial_no, consumer):
    account = get_account()

    tx = contract.functions.assignConsumer(
        serial_no,
        consumer
    ).transact({
        "from": account
    })

    w3.eth.wait_for_transaction_receipt(tx)

    return tx.hex()


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
