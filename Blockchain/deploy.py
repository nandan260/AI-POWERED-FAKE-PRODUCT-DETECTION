from solcx import compile_source, install_solc
from web3 import Web3
import json

install_solc("0.8.19")

with open("contract.sol", "r") as file:
    contract_source = file.read()

compiled_sol = compile_source(
    contract_source,
    output_values=["abi", "bin"],
    solc_version="0.8.19"
)

contract_id, contract_interface = compiled_sol.popitem()

abi = contract_interface["abi"]
bytecode = contract_interface["bin"]

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

account = w3.eth.accounts[0]

ProductVerification = w3.eth.contract(
    abi=abi,
    bytecode=bytecode
)

tx_hash = ProductVerification.constructor().transact({
    "from": account,
    "gas": 5000000,
    "gasPrice": w3.to_wei("20", "gwei")
})

tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

contract_address = tx_receipt.contractAddress

print("Contract Address:", contract_address)

with open("contract_info.json", "w") as f:
    json.dump({
        "address": contract_address,
        "abi": abi
    }, f, indent=4)

print("Contract deployed successfully.")