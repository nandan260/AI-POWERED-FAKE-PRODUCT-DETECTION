
from solcx import compile_source, install_solc
from web3 import Web3
import json
from pathlib import Path

# Connect to local Ganache
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

if not w3.is_connected():
    raise ConnectionError(
        "Ganache is not running at http://127.0.0.1:7545"
    )

# Use the first Ganache account
account = w3.eth.accounts[0]

# Find files inside the Blockchain folder
base_dir = Path(__file__).resolve().parent
contract_path = base_dir / "contract.sol"
info_path = base_dir / "contract_info.json"

# Compile the Solidity contract
install_solc("0.8.19")

with open(contract_path, "r", encoding="utf-8") as file:
    contract_source = file.read()

compiled_sol = compile_source(
    contract_source,
    output_values=["abi", "bin"],
    solc_version="0.8.19"
)

contract_id, contract_interface = compiled_sol.popitem()

ProductVerification = w3.eth.contract(
    abi=contract_interface["abi"],
    bytecode=contract_interface["bin"]
)

# Deploy the contract to Ganache
tx_hash = ProductVerification.constructor().transact({
    "from": account,
    "gas": 5000000
})

tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

if tx_receipt["status"] != 1:
    raise RuntimeError("Contract deployment failed.")

contract_address = tx_receipt.contractAddress

# Save details where blockchain.py expects them
with open(info_path, "w", encoding="utf-8") as file:
    json.dump({
        "address": contract_address,
        "abi": contract_interface["abi"]
    }, file, indent=4)

print("Contract deployed successfully!")
print("Contract Address:", contract_address)
print("Saved details to:", info_path)
