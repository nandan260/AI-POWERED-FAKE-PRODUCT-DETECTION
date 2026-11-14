import fs from "node:fs";
import path from "node:path";

export interface Manufacturer {
  id: number;
  companyName: string;
  email: string;
  password: string;
}

export interface Seller {
  id: number;
  shopName: string;
  email: string;
  password: string;
}

export interface Consumer {
  id: number;
  fullName: string;
  email: string;
  password: string;
}

export type OwnerType = "Manufacturer" | "Seller" | "Consumer";

export interface Product {
  id: number;
  manufacturerId: number;
  brand: string;
  productName: string;
  modelName: string;
  serialNo: string;
  originalImage: string;
  qrCode: string;
  blockchainTx: string;
  currentOwnerType: OwnerType;
  currentOwnerId: number;
  status: string;
}

export interface OwnershipRecord {
  id: number;
  productId: number;
  fromOwnerType: OwnerType;
  fromOwnerId: number;
  toOwnerType: OwnerType;
  toOwnerId: number;
  transferDate: string;
  blockchainHash: string;
}

export interface VerificationStats {
  verifiedCount: number;
  fakeDetectedCount: number;
}

export interface VerificationRecord {
  id: number;
  serialNo: string;
  productName: string;
  brand: string;
  prediction: "genuine" | "fake";
  confidencePercent: number;
  similarityPercent: number;
  finalResult: "GENUINE PRODUCT" | "FAKE PRODUCT" | "MANUAL INSPECTION REQUIRED";
  checkedByConsumerId: number;
  checkedAt: string;
}

const STORE_FILE = path.join(process.cwd(), ".pg_store.json");

class InMemoryStore {
  manufacturers: Manufacturer[] = [
    {
      id: 1,
      companyName: "NIKE",
      email: "nike123@gmail.com",
      password: "nike1234",
    },
  ];

  sellers: Seller[] = [
    {
      id: 1,
      shopName: "ABC ELECTRONICS",
      email: "abc123@gmail.com",
      password: "abc1234",
    },
  ];

  consumers: Consumer[] = [
    {
      id: 1,
      fullName: "NANDAN",
      email: "nandan123@gmail.com",
      password: "nandan1234",
    },
    {
      id: 2,
      fullName: "NANDAN S",
      email: "nike123@gmail.com",
      password: "nike1234",
    },
  ];

  products: Product[] = [
    {
      id: 1,
      manufacturerId: 1,
      brand: "NIKE",
      productName: "NIKE SHOES",
      modelName: "AIR JORDAN",
      serialNo: "1001",
      originalImage: "940d1845f7e544f8b98b937b4d398519.png",
      qrCode: "5c4c18b88b054f3f82b2660c728d6ea6.png",
      blockchainTx:
        "9485af373b0287688132f337d5d0847a77dbc6d2f20cdb53f327b7bb44679b10",
      currentOwnerType: "Consumer",
      currentOwnerId: 1,
      status: "Assigned to Consumer",
    },
    {
      id: 2,
      manufacturerId: 1,
      brand: "NIKE",
      productName: "NIKE SHOES",
      modelName: "AIR JORDAN 5",
      serialNo: "1012",
      originalImage: "11abc6881ee3482fb9789fe5296cfc29.jpg",
      qrCode: "edb66586aa544f5bb4323ac3434e175c.png",
      blockchainTx:
        "696044dfaf4b44bd4f77f2a9f986533577e823a9f64f848d87ffb7c7b5ca748b",
      currentOwnerType: "Consumer",
      currentOwnerId: 1,
      status: "Assigned to Consumer",
    },
    {
      id: 3,
      manufacturerId: 1,
      brand: "NIKE",
      productName: "NIKE SHOES",
      modelName: "AIR JORDAN 9",
      serialNo: "1080",
      originalImage: "9b6360258d614381b958b6bc9f05e9d4.jpg",
      qrCode: "5c407ab433c84946a082afdf62438506.png",
      blockchainTx:
        "ca65e2b833032167224520341ca4382c9b350c0f5ed3e6b6e73a42deecd37695",
      currentOwnerType: "Consumer",
      currentOwnerId: 1,
      status: "Assigned to Consumer",
    },
    {
      id: 4,
      manufacturerId: 1,
      brand: "nike",
      productName: "nike shoes",
      modelName: "air",
      serialNo: "1234567",
      originalImage: "c56d4f9c6eae410caf998e52c7a1231c.jpg",
      qrCode: "e967fbaf76264c7a9dc5457044c39fe0.png",
      blockchainTx:
        "eb7ae9b0b638e22ec553162307a873c3942106717ff19dac076f4fd7c5b44072",
      currentOwnerType: "Consumer",
      currentOwnerId: 1,
      status: "Assigned to Consumer",
    },
    {
      id: 5,
      manufacturerId: 1,
      brand: "NIKE",
      productName: "NIKE SHOES",
      modelName: "Sport",
      serialNo: "4545",
      originalImage: "5bd4ac27b0e64c7fa76daf60c16a5f10.jpeg",
      qrCode: "1bcc1ba226414a6e86fd515b0cf9ca9a.png",
      blockchainTx:
        "246608090d39c16a9420853c5d57c9f03cb666f096ff0d7e4696fddefed51528",
      currentOwnerType: "Manufacturer",
      currentOwnerId: 1,
      status: "Registered",
    },
    {
      id: 6,
      manufacturerId: 1,
      brand: "NIKE",
      productName: "NIKE SHOES",
      modelName: "Sport",
      serialNo: "576858",
      originalImage: "d77f784b0ee445c4bbec4c810dca5ca4.jpg",
      qrCode: "38c5b196f5d34c5b8ed7c6f42b76b61f.png",
      blockchainTx:
        "c95f46fbc4c62667839b9daf09400efe21460ad0df21bba7e95ce332e13e87a3",
      currentOwnerType: "Consumer",
      currentOwnerId: 1,
      status: "Assigned to Consumer",
    },
    {
      id: 7,
      manufacturerId: 1,
      brand: "NIKE",
      productName: "NIKE SHOES",
      modelName: "AIR JORDAN 100",
      serialNo: "1200",
      originalImage: "9292eab825ab4b5db022117fc917f8c2.png",
      qrCode: "ca8ead70b41e48918ef1118bbf94e221.png",
      blockchainTx:
        "d0e8615ff76907c731aae236389f39790db0dfa4f5c195871dbf65fc23f402cc",
      currentOwnerType: "Consumer",
      currentOwnerId: 1,
      status: "Assigned to Consumer",
    },
  ];

  ownershipHistory: OwnershipRecord[] = [
    {
      id: 1,
      productId: 1,
      fromOwnerType: "Manufacturer",
      fromOwnerId: 1,
      toOwnerType: "Seller",
      toOwnerId: 1,
      transferDate: "2026-10-26 07:02:40",
      blockchainHash:
        "079347b111d1e84fc717979a464ed4d7538210a0b7b165f36bb1e1731bf0ae7d",
    },
    {
      id: 2,
      productId: 1,
      fromOwnerType: "Seller",
      fromOwnerId: 1,
      toOwnerType: "Consumer",
      toOwnerId: 1,
      transferDate: "2026-10-26 07:06:09",
      blockchainHash:
        "c75aa8db518cd5e73394ec431beff8aac273d789e0ae6c4ddbd9f48d58dbc060",
    },
    {
      id: 3,
      productId: 2,
      fromOwnerType: "Manufacturer",
      fromOwnerId: 1,
      toOwnerType: "Seller",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:09:34",
      blockchainHash:
        "da00012b66b48385f8f52db2c71fab619bda53744dbad01302cc9e09e5c9927b",
    },
    {
      id: 4,
      productId: 2,
      fromOwnerType: "Seller",
      fromOwnerId: 1,
      toOwnerType: "Consumer",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:10:49",
      blockchainHash:
        "1415c941ff8c0f38f9c8704c8ab7d9a60ac14474143a2c5010f965cae2362b9c",
    },
    {
      id: 5,
      productId: 3,
      fromOwnerType: "Manufacturer",
      fromOwnerId: 1,
      toOwnerType: "Seller",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:26:28",
      blockchainHash:
        "ce3d1573b4b44bc01ae5ea417fc37cfb1c5a8f6b7e68854a55fa8d3cdfbb70bf",
    },
    {
      id: 6,
      productId: 3,
      fromOwnerType: "Seller",
      fromOwnerId: 1,
      toOwnerType: "Consumer",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:27:25",
      blockchainHash:
        "1301103c947422b3cba791191751a36d71b06afd05c6911df58bc7a02cabd778",
    },
    {
      id: 7,
      productId: 4,
      fromOwnerType: "Manufacturer",
      fromOwnerId: 1,
      toOwnerType: "Seller",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:32:02",
      blockchainHash:
        "1a54ede5635d2944b3281f9f91ad453705a459856972afa11ac471e14e7b2ece",
    },
    {
      id: 8,
      productId: 4,
      fromOwnerType: "Seller",
      fromOwnerId: 1,
      toOwnerType: "Consumer",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:33:17",
      blockchainHash:
        "4a04ce39e2e6d8694127ede39fc2052ef354e73117db06e3724c772d548c0cad",
    },
    {
      id: 9,
      productId: 6,
      fromOwnerType: "Manufacturer",
      fromOwnerId: 1,
      toOwnerType: "Seller",
      toOwnerId: 1,
      transferDate: "2026-11-02 04:54:30",
      blockchainHash:
        "dc296e57ffaa730ab02058ad5e00e2f7a55adbd0c5b5402dcc24d50525bfeb1b",
    },
    {
      id: 10,
      productId: 6,
      fromOwnerType: "Seller",
      fromOwnerId: 1,
      toOwnerType: "Consumer",
      toOwnerId: 1,
      transferDate: "2026-11-02 05:08:58",
      blockchainHash:
        "c1cd11c5e40d2612e094d30a4d9944e43e548f3d22c656c9ebdb02175102e653",
    },
    {
      id: 11,
      productId: 7,
      fromOwnerType: "Manufacturer",
      fromOwnerId: 1,
      toOwnerType: "Seller",
      toOwnerId: 1,
      transferDate: "2026-11-08 08:11:08",
      blockchainHash:
        "958593c9a3990de1ebee9688ce9d96aaf735637acd7e8f09da2c072dc38b21d4",
    },
    {
      id: 12,
      productId: 7,
      fromOwnerType: "Seller",
      fromOwnerId: 1,
      toOwnerType: "Consumer",
      toOwnerId: 1,
      transferDate: "2026-11-08 08:11:26",
      blockchainHash:
        "d8ef87419ba41ee87d4e1758e8ce286c3acd7860d7282b96692fc2f31c62c500",
    },
  ];

  verifications: VerificationRecord[] = [
    {
      id: 1,
      serialNo: "1001",
      productName: "NIKE SHOES",
      brand: "NIKE",
      prediction: "genuine",
      confidencePercent: 97.4,
      similarityPercent: 98.2,
      finalResult: "GENUINE PRODUCT",
      checkedByConsumerId: 1,
      checkedAt: "2026-11-08 09:15:00",
    },
    {
      id: 2,
      serialNo: "1012",
      productName: "NIKE SHOES",
      brand: "NIKE",
      prediction: "genuine",
      confidencePercent: 96.8,
      similarityPercent: 95.9,
      finalResult: "GENUINE PRODUCT",
      checkedByConsumerId: 1,
      checkedAt: "2026-11-08 10:42:00",
    },
  ];

  verificationStats: VerificationStats = {
    verifiedCount: 2,
    fakeDetectedCount: 0,
  };

  private nextManufacturerId = 2;
  private nextSellerId = 2;
  private nextConsumerId = 3;
  private nextProductId = 8;
  private nextHistoryId = 13;
  private nextVerificationId = 3;

  constructor() {
    this.load();
  }

  private load(): void {
    try {
      if (!fs.existsSync(STORE_FILE)) return;
      const raw = fs.readFileSync(STORE_FILE, "utf-8");
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.manufacturers)) this.manufacturers = parsed.manufacturers;
      if (Array.isArray(parsed.sellers)) this.sellers = parsed.sellers;
      if (Array.isArray(parsed.consumers)) this.consumers = parsed.consumers;
      if (Array.isArray(parsed.products)) this.products = parsed.products;
      if (Array.isArray(parsed.ownershipHistory)) this.ownershipHistory = parsed.ownershipHistory;
      if (Array.isArray(parsed.verifications)) this.verifications = parsed.verifications;
      if (parsed.verificationStats) this.verificationStats = parsed.verificationStats;
      if (typeof parsed.nextManufacturerId === "number") this.nextManufacturerId = parsed.nextManufacturerId;
      if (typeof parsed.nextSellerId === "number") this.nextSellerId = parsed.nextSellerId;
      if (typeof parsed.nextConsumerId === "number") this.nextConsumerId = parsed.nextConsumerId;
      if (typeof parsed.nextProductId === "number") this.nextProductId = parsed.nextProductId;
      if (typeof parsed.nextHistoryId === "number") this.nextHistoryId = parsed.nextHistoryId;
      if (typeof parsed.nextVerificationId === "number") this.nextVerificationId = parsed.nextVerificationId;
    } catch (err) {
      console.error("Failed to load store file:", err);
    }
  }

  save(): void {
    try {
      const data = {
        manufacturers: this.manufacturers,
        sellers: this.sellers,
        consumers: this.consumers,
        products: this.products,
        ownershipHistory: this.ownershipHistory,
        verifications: this.verifications,
        verificationStats: this.verificationStats,
        nextManufacturerId: this.nextManufacturerId,
        nextSellerId: this.nextSellerId,
        nextConsumerId: this.nextConsumerId,
        nextProductId: this.nextProductId,
        nextHistoryId: this.nextHistoryId,
        nextVerificationId: this.nextVerificationId,
      };
      fs.writeFileSync(STORE_FILE, JSON.stringify(data, null, 2), "utf-8");
    } catch (err) {
      console.error("Failed to save store file:", err);
    }
  }

  addManufacturer(companyName: string, email: string, password: string): Manufacturer {
    const item: Manufacturer = {
      id: this.nextManufacturerId++,
      companyName,
      email,
      password,
    };
    this.manufacturers.push(item);
    this.save();
    return item;
  }

  addSeller(shopName: string, email: string, password: string): Seller {
    const item: Seller = {
      id: this.nextSellerId++,
      shopName,
      email,
      password,
    };
    this.sellers.push(item);
    this.save();
    return item;
  }

  addConsumer(fullName: string, email: string, password: string): Consumer {
    const item: Consumer = {
      id: this.nextConsumerId++,
      fullName,
      email,
      password,
    };
    this.consumers.push(item);
    this.save();
    return item;
  }

  addProduct(input: Omit<Product, "id">): Product {
    const item: Product = {
      id: this.nextProductId++,
      ...input,
    };
    this.products.push(item);
    this.save();
    return item;
  }

  addOwnershipRecord(input: Omit<OwnershipRecord, "id" | "transferDate">): OwnershipRecord {
    const now = new Date();
    const transferDate = now.toISOString().replace("T", " ").slice(0, 19);
    const item: OwnershipRecord = {
      id: this.nextHistoryId++,
      transferDate,
      ...input,
    };
    this.ownershipHistory.push(item);
    this.save();
    return item;
  }

  addVerificationRecord(
    input: Omit<VerificationRecord, "id" | "checkedAt">
  ): VerificationRecord {
    const now = new Date();
    const checkedAt = now.toISOString().replace("T", " ").slice(0, 19);
    const item: VerificationRecord = {
      id: this.nextVerificationId++,
      checkedAt,
      ...input,
    };
    this.verifications.unshift(item);
    this.save();
    return item;
  }
}

export const store = new InMemoryStore();
