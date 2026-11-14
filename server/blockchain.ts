import crypto from "node:crypto";
import { store } from "./store.ts";

export interface BlockchainProductState {
  serialNo: string;
  manufacturer: string;
  seller: string;
  consumer: string;
  exists: boolean;
}

const ledger = new Map<string, BlockchainProductState>();

function seedLedgerFromStore(): void {
  for (const product of store.products) {
    const history = store.ownershipHistory.filter(
      (h) => h.productId === product.id
    );
    const sellerTransfer = history.find((h) => h.toOwnerType === "Seller");
    const consumerTransfer = history.find((h) => h.toOwnerType === "Consumer");

    ledger.set(product.serialNo, {
      serialNo: product.serialNo,
      manufacturer: product.brand,
      seller: sellerTransfer ? String(sellerTransfer.toOwnerId) : "",
      consumer: consumerTransfer ? String(consumerTransfer.toOwnerId) : "",
      exists: true,
    });
  }
}

seedLedgerFromStore();

function createTxHash(payload: string): string {
  return crypto
    .createHash("sha256")
    .update(`${payload}:${Date.now()}:${Math.random()}`)
    .digest("hex");
}

export function registerProductOnChain(
  serialNo: string,
  manufacturer: string
): string {
  ledger.set(serialNo, {
    serialNo,
    manufacturer,
    seller: "",
    consumer: "",
    exists: true,
  });
  return createTxHash(`register:${serialNo}:${manufacturer}`);
}

export function assignSellerOnChain(serialNo: string, seller: string): string {
  const existing = ledger.get(serialNo);
  if (existing) {
    existing.seller = String(seller);
  } else {
    ledger.set(serialNo, {
      serialNo,
      manufacturer: "",
      seller: String(seller),
      consumer: "",
      exists: true,
    });
  }
  return createTxHash(`assignSeller:${serialNo}:${seller}`);
}

export function assignConsumerOnChain(
  serialNo: string,
  consumer: string
): string {
  const existing = ledger.get(serialNo);
  if (existing) {
    existing.consumer = String(consumer);
  } else {
    ledger.set(serialNo, {
      serialNo,
      manufacturer: "",
      seller: "",
      consumer: String(consumer),
      exists: true,
    });
  }
  return createTxHash(`assignConsumer:${serialNo}:${consumer}`);
}

export function verifyProductOnChain(
  serialNo: string
): BlockchainProductState {
  const record = ledger.get(serialNo);
  if (!record) {
    return {
      serialNo,
      manufacturer: "",
      seller: "",
      consumer: "",
      exists: false,
    };
  }
  return { ...record };
}
