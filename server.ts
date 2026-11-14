import "dotenv/config";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import express from "express";
import type { Request, Response } from "express";
import session from "express-session";
import multer from "multer";
import QRCode from "qrcode";

import { compareImages, predictImage } from "./server/ai.ts";
import {
  assignConsumerOnChain,
  assignSellerOnChain,
  registerProductOnChain,
  verifyProductOnChain,
} from "./server/blockchain.ts";
import { store } from "./server/store.ts";

declare module "express-session" {
  interface SessionData {
    manufacturer_id?: number;
    company_name?: string;
    seller_id?: number;
    shop_name?: string;
    consumer_id?: number;
    full_name?: string;
    email?: string;
    admin?: boolean;
    // Role of the most recent sign-in; decides which workspace shared pages (e.g. /history) show.
    active_role?: "manufacturer" | "seller" | "consumer" | "admin";
  }
}

const app = express();
const PORT = 3000;
const ROOT_DIR = process.cwd();

const productImagesDir = path.join(ROOT_DIR, "static", "product_images");
const qrCodesDir = path.join(ROOT_DIR, "static", "qr_codes");
const uploadedImagesDir = path.join(ROOT_DIR, "static", "uploaded_images");

fs.mkdirSync(productImagesDir, { recursive: true });
fs.mkdirSync(qrCodesDir, { recursive: true });
fs.mkdirSync(uploadedImagesDir, { recursive: true });

app.set("trust proxy", 1);
app.set("view engine", "ejs");
app.set("views", path.join(ROOT_DIR, "views"));

app.use("/static", express.static(path.join(ROOT_DIR, "static")));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

const SESSION_SECRET = process.env.SESSION_SECRET || "mysecretkey";
const SESSION_TTL_MS = 1000 * 60 * 60 * 24 * 7; // 7 days
const AUTH_COOKIE_NAME = "pg_auth";

interface AuthPayload {
  manufacturer_id?: number;
  company_name?: string;
  seller_id?: number;
  shop_name?: string;
  consumer_id?: number;
  full_name?: string;
  email?: string;
  admin?: boolean;
  active_role?: "manufacturer" | "seller" | "consumer" | "admin";
  exp: number;
}

function isHttpsRequest(req: Request): boolean {
  const xfProto = String(req.headers["x-forwarded-proto"] || "").toLowerCase();
  return req.secure || xfProto.includes("https") || req.protocol === "https";
}

function hasAuthenticatedSession(
  s: Partial<session.SessionData> | undefined
): boolean {
  if (!s) return false;
  return Boolean(s.manufacturer_id || s.seller_id || s.consumer_id || s.admin);
}

function extractAuthPayload(
  s: Partial<session.SessionData> | undefined
): AuthPayload | null {
  if (!s) return null;
  const payload: AuthPayload = { exp: Date.now() + SESSION_TTL_MS };
  if (typeof s.manufacturer_id === "number") payload.manufacturer_id = s.manufacturer_id;
  if (typeof s.company_name === "string" && s.company_name) payload.company_name = s.company_name;
  if (typeof s.seller_id === "number") payload.seller_id = s.seller_id;
  if (typeof s.shop_name === "string" && s.shop_name) payload.shop_name = s.shop_name;
  if (typeof s.consumer_id === "number") payload.consumer_id = s.consumer_id;
  if (typeof s.full_name === "string" && s.full_name) payload.full_name = s.full_name;
  if (typeof s.email === "string" && s.email) payload.email = s.email;
  if (s.admin === true) payload.admin = true;
  if (s.active_role) payload.active_role = s.active_role;
  if (!hasAuthenticatedSession(payload)) return null;
  return payload;
}

function signAuthToken(s: Partial<session.SessionData> | undefined): string {
  const payload = extractAuthPayload(s);
  if (!payload) return "";
  const encoded = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const sig = crypto
    .createHmac("sha256", SESSION_SECRET)
    .update(encoded)
    .digest("base64url");
  return `${encoded}.${sig}`;
}

function verifyAuthToken(token: string): AuthPayload | null {
  if (!token || typeof token !== "string") return null;
  const dotIdx = token.lastIndexOf(".");
  if (dotIdx <= 0) return null;
  const encoded = token.slice(0, dotIdx);
  const sig = token.slice(dotIdx + 1);
  const expected = crypto
    .createHmac("sha256", SESSION_SECRET)
    .update(encoded)
    .digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const parsed = JSON.parse(
      Buffer.from(encoded, "base64url").toString("utf8")
    ) as AuthPayload;
    if (!parsed || typeof parsed.exp !== "number" || parsed.exp <= Date.now()) {
      return null;
    }
    if (!hasAuthenticatedSession(parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function applyAuthPayloadToSession(
  sess: Partial<session.SessionData>,
  payload: AuthPayload
): void {
  if (payload.manufacturer_id) sess.manufacturer_id = payload.manufacturer_id;
  if (payload.company_name) sess.company_name = payload.company_name;
  if (payload.seller_id) sess.seller_id = payload.seller_id;
  if (payload.shop_name) sess.shop_name = payload.shop_name;
  if (payload.consumer_id) sess.consumer_id = payload.consumer_id;
  if (payload.full_name) sess.full_name = payload.full_name;
  if (payload.email) sess.email = payload.email;
  if (payload.admin) sess.admin = true;
  if (payload.active_role) sess.active_role = payload.active_role;
}

function parseCookieValue(cookieHeader: string | undefined, name: string): string {
  if (!cookieHeader) return "";
  for (const part of cookieHeader.split(";")) {
    const eqIdx = part.indexOf("=");
    if (eqIdx <= 0) continue;
    if (part.slice(0, eqIdx).trim() === name) {
      const raw = part.slice(eqIdx + 1).trim();
      try {
        return decodeURIComponent(raw);
      } catch {
        return raw;
      }
    }
  }
  return "";
}

function setAuthCookie(req: Request, res: Response, token: string): void {
  if (!token) return;
  const isHttps = isHttpsRequest(req);
  res.cookie(AUTH_COOKIE_NAME, token, {
    httpOnly: true,
    maxAge: SESSION_TTL_MS,
    path: "/",
    sameSite: isHttps ? "none" : "lax",
    secure: isHttps,
  });
}

function clearAuthCookie(req: Request, res: Response): void {
  const isHttps = isHttpsRequest(req);
  res.clearCookie(AUTH_COOKIE_NAME, {
    httpOnly: true,
    path: "/",
    sameSite: isHttps ? "none" : "lax",
    secure: isHttps,
  });
}

function redirectAfterAuth(req: Request, res: Response, targetPath: string): void {
  const role = targetPath.split("/")[1];
  if (role === "manufacturer" || role === "seller" || role === "consumer" || role === "admin") {
    req.session.active_role = role;
  }
  const token = signAuthToken(req.session);
  setAuthCookie(req, res, token);
  req.session.save((err) => {
    if (err) {
      console.error("Session save error:", err);
    }
    const sep = targetPath.includes("?") ? "&" : "?";
    res.redirect(`${targetPath}${sep}_auth=${encodeURIComponent(token)}`);
  });
}

function redirectPreservingFallback(
  _req: Request,
  res: Response,
  targetPath: string
): void {
  const token = String(res.locals.fallbackAuthToken || "");
  if (!token) {
    res.redirect(targetPath);
    return;
  }
  const sep = targetPath.includes("?") ? "&" : "?";
  res.redirect(`${targetPath}${sep}_auth=${encodeURIComponent(token)}`);
}

function clearAuthSession(
  req: Request,
  res: Response,
  keys: Array<keyof session.SessionData>,
  redirectPath: string
): void {
  for (const key of keys) {
    delete req.session[key];
  }
  const remainingToken = signAuthToken(req.session);
  if (remainingToken) {
    setAuthCookie(req, res, remainingToken);
    req.session.save(() => {
      const sep = redirectPath.includes("?") ? "&" : "?";
      res.redirect(`${redirectPath}${sep}_auth=${encodeURIComponent(remainingToken)}`);
    });
    return;
  }
  clearAuthCookie(req, res);
  req.session.save(() => {
    const sep = redirectPath.includes("?") ? "&" : "?";
    res.redirect(`${redirectPath}${sep}logged_out=1`);
  });
}

// Add Partitioned attribute (CHIPS) on HTTPS so Chrome iframes accept session & auth cookies
app.use((req, res, next) => {
  if (isHttpsRequest(req)) {
    const origSetHeader = res.setHeader.bind(res);
    res.setHeader = ((
      name: string,
      value: number | string | readonly string[]
    ) => {
      if (name.toLowerCase() === "set-cookie") {
        const patch = (c: string) =>
          (c.startsWith("connect.sid=") || c.startsWith(`${AUTH_COOKIE_NAME}=`)) &&
          !/;\s*Partitioned\b/i.test(c)
            ? `${c}; Partitioned`
            : c;
        value = Array.isArray(value) ? value.map(patch) : patch(String(value));
      }
      return origSetHeader(name, value);
    }) as typeof res.setHeader;
  }
  next();
});

app.use(
  session({
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      maxAge: SESSION_TTL_MS,
      sameSite: "lax",
    },
  })
);

// Adapt cookie security dynamically for HTTPS iframe previews vs local HTTP
app.use((req, _res, next) => {
  if (isHttpsRequest(req) && req.session?.cookie) {
    req.session.cookie.secure = true;
    req.session.cookie.sameSite = "none";
  }
  next();
});

// Durable session hydration from signed pg_auth cookie or _auth token (survives restarts & cookie blocks)
app.use((req: Request, res: Response, next) => {
  const cookieToken = parseCookieValue(req.headers.cookie, AUTH_COOKIE_NAME);
  const cookiePayload = cookieToken ? verifyAuthToken(cookieToken) : null;
  const hasConnectSid = Boolean(parseCookieValue(req.headers.cookie, "connect.sid"));
  const browserSupportsCookies = Boolean(cookiePayload || (hasConnectSid && hasAuthenticatedSession(req.session)));

  const rawToken =
    (typeof req.query._auth === "string" && req.query._auth) ||
    (req.body && typeof req.body._auth === "string" && req.body._auth) ||
    (typeof req.headers["x-auth-token"] === "string" && req.headers["x-auth-token"]) ||
    "";

  if (!hasAuthenticatedSession(req.session)) {
    const payload = cookiePayload || (rawToken ? verifyAuthToken(rawToken) : null);
    if (payload) {
      applyAuthPayloadToSession(req.session, payload);
    }
  }

  const isAuthenticated = hasAuthenticatedSession(req.session);
  res.locals.usingCookieAuth = isAuthenticated && browserSupportsCookies;

  if (isAuthenticated) {
    const freshToken = signAuthToken(req.session);
    if (!cookiePayload) {
      setAuthCookie(req, res, freshToken);
    }
    if (browserSupportsCookies && req.method === "GET" && typeof req.query._auth === "string") {
      const url = new URL(req.originalUrl, "http://localhost");
      url.searchParams.delete("_auth");
      const cleanUrl = url.pathname + (url.search ? url.search : "");
      return res.redirect(cleanUrl);
    }
    res.locals.fallbackAuthToken = browserSupportsCookies ? "" : freshToken;
  } else {
    res.locals.fallbackAuthToken = "";
  }

  next();
});

const productImageUpload = multer({
  storage: multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, productImagesDir),
    filename: (_req, file, cb) => {
      const ext = path.extname(file.originalname) || ".png";
      cb(null, `${crypto.randomUUID().replace(/-/g, "")}${ext}`);
    },
  }),
});

const consumerImageUpload = multer({
  storage: multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, uploadedImagesDir),
    filename: (_req, file, cb) => {
      const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
      cb(null, `${crypto.randomUUID()}_${safeName}`);
    },
  }),
});

function getBaseUrl(req: Request): string {
  if (process.env.APP_URL && process.env.APP_URL !== "MY_APP_URL") {
    return process.env.APP_URL.replace(/\/+$/, "");
  }
  const proto =
    (req.headers["x-forwarded-proto"] as string) || req.protocol || "http";
  const host = req.get("host") || `localhost:${PORT}`;
  return `${proto}://${host}`;
}

interface WorkspaceNavLink {
  label: string;
  href: string;
  icon: string;
}

interface WorkspaceContext {
  role: "manufacturer" | "seller" | "consumer" | "admin";
  roleLabel: string;
  accountName: string;
  initials: string;
  activePath: string;
  logoutHref: string;
  links: WorkspaceNavLink[];
  primaryAction: { label: string; href: string; icon: string } | null;
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "U";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function getWorkspaceContext(req: Request): WorkspaceContext | null {
  const p = req.path;

  const makeManufacturer = (): WorkspaceContext => {
    const name = req.session.company_name || "Manufacturer";
    return {
      role: "manufacturer",
      roleLabel: "Manufacturer",
      accountName: name,
      initials: initialsOf(name),
      activePath: p,
      logoutHref: "/manufacturer/logout",
      links: [
        { label: "Dashboard", href: "/manufacturer/dashboard", icon: "grid" },
        { label: "Products", href: "/manufacturer/products", icon: "package" },
        { label: "Register", href: "/register", icon: "plus" },
        { label: "Assign Seller", href: "/manufacturer/assign", icon: "users" },
        { label: "Ledger", href: "/history", icon: "link" },
      ],
      primaryAction: { label: "+ Register product", href: "/register", icon: "plus" },
    };
  };

  const makeSeller = (): WorkspaceContext => {
    const name = req.session.shop_name || "Seller";
    return {
      role: "seller",
      roleLabel: "Seller",
      accountName: name,
      initials: initialsOf(name),
      activePath: p,
      logoutHref: "/seller/logout",
      links: [
        { label: "Overview", href: "/seller/dashboard", icon: "grid" },
        { label: "Inventory", href: "/seller/dashboard?view=inventory", icon: "clipboard" },
        { label: "Assign Buyer", href: "/seller/dashboard?view=assign", icon: "user" },
        { label: "Ledger", href: "/seller/dashboard?view=ledger", icon: "link" },
      ],
      primaryAction: { label: "Assign buyer", href: "/seller/dashboard?view=assign", icon: "user" },
    };
  };

  const makeConsumer = (): WorkspaceContext => {
    const name = req.session.full_name || "Consumer";
    return {
      role: "consumer",
      roleLabel: "Consumer",
      accountName: name,
      initials: initialsOf(name),
      activePath: p,
      logoutHref: "/consumer/logout",
      links: [
        { label: "Overview", href: "/consumer/dashboard", icon: "grid" },
        { label: "My Products", href: "/consumer/dashboard?view=products", icon: "package" },
        { label: "Verify AI", href: "/consumer/dashboard?view=verify", icon: "cpu" },
        { label: "Lookup", href: "/consumer/dashboard?view=lookup", icon: "search" },
      ],
      primaryAction: { label: "Verify AI", href: "/consumer/dashboard?view=verify", icon: "cpu" },
    };
  };

  const makeAdmin = (): WorkspaceContext => ({
    role: "admin",
    roleLabel: "Admin",
    accountName: "System Admin",
    initials: "AD",
    activePath: p,
    logoutHref: "/admin/logout",
    links: [
      { label: "Overview", href: "/admin/dashboard", icon: "grid" },
      { label: "Ledger", href: "/history", icon: "link" },
      { label: "Lookup", href: "/verify", icon: "search" },
    ],
    primaryAction: { label: "Ledger", href: "/history", icon: "link" },
  });

  if ((p.startsWith("/manufacturer") || p === "/register") && req.session.manufacturer_id) {
    return makeManufacturer();
  }
  if (p.startsWith("/seller") && req.session.seller_id) {
    return makeSeller();
  }
  if ((p.startsWith("/consumer") || p === "/verify-image") && req.session.consumer_id) {
    return makeConsumer();
  }
  if (p.startsWith("/admin") && req.session.admin) {
    return makeAdmin();
  }

  const active = req.session.active_role;
  if (active === "manufacturer" && req.session.manufacturer_id) return makeManufacturer();
  if (active === "seller" && req.session.seller_id) return makeSeller();
  if (active === "consumer" && req.session.consumer_id) return makeConsumer();
  if (active === "admin" && req.session.admin) return makeAdmin();

  if (req.session.manufacturer_id) return makeManufacturer();
  if (req.session.seller_id) return makeSeller();
  if (req.session.consumer_id) return makeConsumer();
  if (req.session.admin) return makeAdmin();
  return null;
}

app.use((req: Request, res: Response, next) => {
  res.locals.workspace = getWorkspaceContext(req);
  next();
});

function buildDashboardAnalytics(
  scopedProducts: typeof store.products,
  _scopedHistory: typeof store.ownershipHistory,
  scopedVerifications: typeof store.verifications
) {
  const total = scopedProducts.length;
  const regCount = scopedProducts.filter((p) => p.currentOwnerType === "Manufacturer").length;
  const sellerCount = scopedProducts.filter((p) => p.currentOwnerType === "Seller").length;
  const consumerCount = scopedProducts.filter((p) => p.currentOwnerType === "Consumer").length;

  const pct = (n: number) => (total === 0 ? 0 : Math.round((n / total) * 100));

  const stages = [
    { label: "Registered", count: regCount, percent: pct(regCount), color: "#677E8A" },
    { label: "With Seller", count: sellerCount, percent: pct(sellerCount), color: "#2B4A51" },
    { label: "With Consumer", count: consumerCount, percent: pct(consumerCount), color: "#122E34" },
  ];

  const genuine = scopedVerifications.filter((v) => v.finalResult === "GENUINE PRODUCT").length;
  const manual = scopedVerifications.filter((v) => v.finalResult === "MANUAL INSPECTION REQUIRED").length;
  const fake = scopedVerifications.filter((v) => v.finalResult === "FAKE PRODUCT").length;

  return {
    stages,
    verificationSummary: { genuine, manual, fake },
  };
}

// Home
app.get("/", (_req: Request, res: Response) => {
  res.render("index");
});

app.get("/login", (_req: Request, res: Response) => {
  res.redirect("/manufacturer/login");
});

// Direct dashboard entry (uses active session or opens seeded demo workspace)
app.get("/dashboard", (req: Request, res: Response) => {
  const requestedRole = String(req.query.role || "").trim().toLowerCase();

  if (!requestedRole) {
    if (req.session.manufacturer_id) return redirectPreservingFallback(req, res, "/manufacturer/dashboard");
    if (req.session.seller_id) return redirectPreservingFallback(req, res, "/seller/dashboard");
    if (req.session.consumer_id) return redirectPreservingFallback(req, res, "/consumer/dashboard");
    if (req.session.admin) return redirectPreservingFallback(req, res, "/admin/dashboard");
  }

  const targetRole = requestedRole || "manufacturer";
  if (targetRole === "seller" && store.sellers[0]) {
    req.session.seller_id = store.sellers[0].id;
    req.session.shop_name = store.sellers[0].shopName;
    req.session.email = store.sellers[0].email;
    return redirectAfterAuth(req, res, "/seller/dashboard");
  }
  if (targetRole === "consumer" && store.consumers[0]) {
    req.session.consumer_id = store.consumers[0].id;
    req.session.full_name = store.consumers[0].fullName;
    req.session.email = store.consumers[0].email;
    return redirectAfterAuth(req, res, "/consumer/dashboard");
  }
  if (targetRole === "admin") {
    req.session.admin = true;
    return redirectAfterAuth(req, res, "/admin/dashboard");
  }

  if (store.manufacturers[0]) {
    req.session.manufacturer_id = store.manufacturers[0].id;
    req.session.company_name = store.manufacturers[0].companyName;
    req.session.email = store.manufacturers[0].email;
    return redirectAfterAuth(req, res, "/manufacturer/dashboard");
  }

  return res.redirect("/manufacturer/login");
});

// ==================== MANUFACTURER ROUTES ====================

app.get("/manufacturer/login", (_req: Request, res: Response) => {
  res.render("manufacturer_login", { error: null });
});

app.post("/manufacturer/login", (req: Request, res: Response) => {
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");

  const manufacturer = store.manufacturers.find(
    (m) => m.email.toLowerCase() === email && m.password === password
  );

  if (!manufacturer) {
    return res
      .status(401)
      .render("manufacturer_login", { error: "Invalid Email or Password" });
  }

  req.session.manufacturer_id = manufacturer.id;
  req.session.company_name = manufacturer.companyName;
  req.session.email = manufacturer.email;
  return redirectAfterAuth(req, res, "/manufacturer/dashboard");
});

app.get("/manufacturer/register", (_req: Request, res: Response) => {
  res.render("manufacturer_register", { error: null });
});

app.post("/manufacturer/register", (req: Request, res: Response) => {
  const companyName = String(req.body.company_name || "").trim();
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");

  if (!companyName || !email || !password) {
    return res
      .status(400)
      .render("manufacturer_register", { error: "All fields are required." });
  }

  const existing = store.manufacturers.find(
    (m) => m.email.toLowerCase() === email
  );
  if (existing) {
    return res.status(409).render("manufacturer_register", {
      error: "Email already registered.",
    });
  }

  store.addManufacturer(companyName, email, password);
  return res.redirect("/manufacturer/login");
});

app.get("/manufacturer/dashboard", (req: Request, res: Response) => {
  if (!req.session.manufacturer_id || !req.session.company_name) {
    return res.redirect("/manufacturer/login");
  }

  const manufacturerId = req.session.manufacturer_id;
  const myProducts = store.products.filter(
    (p) => p.manufacturerId === manufacturerId
  );
  const myProductIds = new Set(myProducts.map((p) => p.id));
  const mySerials = new Set(myProducts.map((p) => p.serialNo));
  const myHistory = store.ownershipHistory.filter((h) => myProductIds.has(h.productId));
  const myVerifications = store.verifications.filter((v) => mySerials.has(v.serialNo));
  const myTxCount =
    myProducts.filter((p) => Boolean(p.blockchainTx)).length + myHistory.length;

  const analytics = buildDashboardAnalytics(myProducts, myHistory, myVerifications);

  const productById = new Map(myProducts.map((p) => [p.id, p]));
  const historyNewestFirst = [...myHistory].sort((a, b) =>
    b.transferDate.localeCompare(a.transferDate)
  );
  const latest = historyNewestFirst[0];
  const latestProduct = latest ? productById.get(latest.productId) : undefined;

  // Transfers grouped by day of week (Sun..Sat) across all of this manufacturer's history.
  const weekdayCounts = [0, 0, 0, 0, 0, 0, 0];
  for (const h of myHistory) {
    const day = new Date(h.transferDate.replace(" ", "T")).getDay();
    if (!Number.isNaN(day)) weekdayCounts[day] += 1;
  }

  const withConsumer = myProducts.filter((p) => p.currentOwnerType === "Consumer").length;
  const withSeller = myProducts.filter((p) => p.currentOwnerType === "Seller").length;
  const lastHash = latest?.blockchainHash || [...myProducts].reverse().find((p) => p.blockchainTx)?.blockchainTx || "";

  const dash = {
    companyName: req.session.company_name,
    total: myProducts.length,
    genuine: analytics.verificationSummary.genuine,
    withConsumer,
    withSeller,
    registered: myProducts.length - withConsumer - withSeller,
    flagged: analytics.verificationSummary.fake + analytics.verificationSummary.manual,
    consumerPercent: myProducts.length ? Math.round((withConsumer / myProducts.length) * 100) : 0,
    weekdayCounts,
    latestTransfer: latest && latestProduct
      ? { serialNo: latestProduct.serialNo, toOwnerType: latest.toOwnerType, date: latest.transferDate }
      : null,
    txCount: myTxCount,
    lastHash,
    products: [...myProducts].reverse().map((p) => ({
      id: p.id,
      serialNo: p.serialNo,
      productName: p.productName,
      modelName: p.modelName,
      image: p.originalImage,
      owner: p.currentOwnerType,
      status: p.status,
      blockchainTx: p.blockchainTx,
    })),
  };

  res.render("manufacturer_dashboard", {
    dash,
    pageTitle: "Manufacturer Dashboard",
    pageHeading: "Overview",
    headingTitle: `${req.session.company_name} Workspace`,
    headingSub: "Monitor registered products, custody transfers, and AI verifications.",
    tableTitle: "Registered Products",
    totalProductsCount: myProducts.length,
    products: myProducts,
    kpis: [
      { label: "Total Products", value: myProducts.length, foot: "Registered batches", icon: "package" },
      { label: "Verified Genuine", value: analytics.verificationSummary.genuine, foot: "Passed AI check", icon: "check" },
      { label: "Flagged / Review", value: analytics.verificationSummary.fake + analytics.verificationSummary.manual, foot: "Requires inspection", icon: "alert" },
      { label: "Blockchain TXs", value: myTxCount, foot: "Anchored on-chain", icon: "link" },
    ],
    ...analytics,
  });
});

app.get("/manufacturer/products", (req: Request, res: Response) => {
  if (!req.session.manufacturer_id) {
    return res.redirect("/manufacturer/login");
  }

  const products = store.products.filter(
    (p) => p.manufacturerId === req.session.manufacturer_id
  );
  res.render("manufacturer_products", { products });
});

app.get("/manufacturer/assign", (req: Request, res: Response) => {
  if (!req.session.manufacturer_id) {
    return res.redirect("/manufacturer/login");
  }

  const products = store.products.filter(
    (p) =>
      p.manufacturerId === req.session.manufacturer_id &&
      p.currentOwnerType === "Manufacturer"
  );
  res.render("manufacturer_assign", {
    products,
    sellers: store.sellers,
  });
});

app.post("/manufacturer/assign-product", (req: Request, res: Response) => {
  if (!req.session.manufacturer_id) {
    return res.redirect("/manufacturer/login");
  }

  const productId = Number(req.body.product_id);
  const sellerId = Number(req.body.seller_id);
  const manufacturerId = req.session.manufacturer_id;

  const product = store.products.find(
    (p) => p.id === productId && p.manufacturerId === manufacturerId
  );
  if (!product) {
    return res.status(404).send("Invalid Product");
  }

  const seller = store.sellers.find((s) => s.id === sellerId);
  if (!seller) {
    return res.status(404).send("Invalid Seller");
  }

  product.currentOwnerType = "Seller";
  product.currentOwnerId = sellerId;
  product.status = "Assigned";

  const txHash = assignSellerOnChain(product.serialNo, String(sellerId));
  store.addOwnershipRecord({
    productId: product.id,
    fromOwnerType: "Manufacturer",
    fromOwnerId: manufacturerId,
    toOwnerType: "Seller",
    toOwnerId: sellerId,
    blockchainHash: txHash,
  });

  return redirectPreservingFallback(
    req,
    res,
    `/manufacturer/assign?toast=${encodeURIComponent(`Assigned #${product.serialNo} to seller`)}`
  );
});

app.get("/manufacturer/logout", (req: Request, res: Response) => {
  clearAuthSession(
    req,
    res,
    ["manufacturer_id", "company_name", "email"],
    "/manufacturer/login"
  );
});

app.get("/manufacturer/history/:productId", (req: Request, res: Response) => {
  const productId = Number(req.params.productId);
  const history = store.ownershipHistory.filter(
    (h) => h.productId === productId
  );
  res.render("timeline", { history });
});

// ==================== PRODUCT REGISTRATION ====================

app.get("/register", (req: Request, res: Response) => {
  if (!req.session.manufacturer_id) {
    return res.redirect("/manufacturer/login");
  }
  res.render("register", { error: null });
});

app.post(
  "/register",
  productImageUpload.single("original_image"),
  async (req: Request, res: Response) => {
    if (!req.session.manufacturer_id) {
      return res.redirect("/manufacturer/login");
    }

    const brand = String(req.body.brand || "").trim();
    const productName = String(req.body.product_name || "").trim();
    const modelName = String(req.body.model_name || "").trim();
    const serialNo = String(req.body.serial_no || "").trim();
    const file = req.file;

    if (!file) {
      return res
        .status(400)
        .render("register", { error: "Please select a product image." });
    }

    const existing = store.products.find((p) => p.serialNo === serialNo);
    if (existing) {
      if (fs.existsSync(file.path)) {
        fs.unlinkSync(file.path);
      }
      return res.status(409).render("register", {
        error:
          "This serial number is already registered. Please use a unique serial number.",
      });
    }

    const txHash = registerProductOnChain(serialNo, brand);

    const qrFilename = `${crypto.randomUUID().replace(/-/g, "")}.png`;
    const qrPath = path.join(qrCodesDir, qrFilename);
    const verifyUrl = `${getBaseUrl(req)}/verify/${encodeURIComponent(serialNo)}`;
    await QRCode.toFile(qrPath, verifyUrl, { width: 300, margin: 2 });

    store.addProduct({
      manufacturerId: req.session.manufacturer_id,
      brand,
      productName,
      modelName,
      serialNo,
      originalImage: file.filename,
      qrCode: qrFilename,
      blockchainTx: txHash,
      currentOwnerType: "Manufacturer",
      currentOwnerId: req.session.manufacturer_id,
      status: "Registered",
    });

    return redirectPreservingFallback(
      req,
      res,
      `/manufacturer/products?toast=${encodeURIComponent(`Registered #${serialNo}`)}`
    );
  }
);

// ==================== SELLER ROUTES ====================

app.get("/seller/register", (_req: Request, res: Response) => {
  res.render("seller_register", { error: null });
});

app.post("/seller/register", (req: Request, res: Response) => {
  const shopName = String(req.body.shop_name || "").trim();
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");

  if (!shopName || !email || !password) {
    return res
      .status(400)
      .render("seller_register", { error: "All fields are required." });
  }

  const existing = store.sellers.find((s) => s.email.toLowerCase() === email);
  if (existing) {
    return res
      .status(409)
      .render("seller_register", { error: "Email already registered." });
  }

  store.addSeller(shopName, email, password);
  return res.redirect("/seller/login");
});

app.get("/seller/login", (_req: Request, res: Response) => {
  res.render("seller_login", { error: null });
});

app.post("/seller/login", (req: Request, res: Response) => {
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");

  const seller = store.sellers.find(
    (s) => s.email.toLowerCase() === email && s.password === password
  );

  if (!seller) {
    return res
      .status(401)
      .render("seller_login", { error: "Invalid Email or Password" });
  }

  req.session.seller_id = seller.id;
  req.session.shop_name = seller.shopName;
  req.session.email = seller.email;
  return redirectAfterAuth(req, res, "/seller/dashboard");
});

app.get("/seller/dashboard", (req: Request, res: Response) => {
  if (!req.session.seller_id || !req.session.shop_name) {
    return res.redirect("/seller/login");
  }

  const sellerId = req.session.seller_id;
  const sellerProductIds = new Set(
    store.ownershipHistory
      .filter((h) => h.toOwnerType === "Seller" && h.toOwnerId === sellerId)
      .map((h) => h.productId)
  );
  const sellerProducts = store.products.filter(
    (p) =>
      (p.currentOwnerType === "Seller" && p.currentOwnerId === sellerId) ||
      sellerProductIds.has(p.id)
  );
  const sellerHistory = store.ownershipHistory.filter(
    (h) =>
      (h.toOwnerType === "Seller" && h.toOwnerId === sellerId) ||
      (h.fromOwnerType === "Seller" && h.fromOwnerId === sellerId)
  );
  const sellerSerials = new Set(sellerProducts.map((p) => p.serialNo));
  const sellerVerifications = store.verifications.filter((v) =>
    sellerSerials.has(v.serialNo)
  );
  const heldCount = sellerProducts.filter(
    (p) => p.currentOwnerType === "Seller" && p.currentOwnerId === sellerId
  ).length;

  const analytics = buildDashboardAnalytics(
    sellerProducts,
    sellerHistory,
    sellerVerifications
  );

  const productById = new Map(store.products.map((p) => [p.id, p]));
  const consumerName = new Map(store.consumers.map((c) => [c.id, c.fullName]));
  const ownerName = (type: string, id: number): string => {
    if (type === "Manufacturer") return store.manufacturers.find((m) => m.id === id)?.companyName || "Manufacturer";
    if (type === "Seller") return store.sellers.find((s) => s.id === id)?.shopName || "Seller";
    return consumerName.get(id) || "Consumer";
  };

  const dash = {
    shopName: req.session.shop_name,
    stats: {
      total: sellerProducts.length,
      inStock: heldCount,
      genuine: analytics.verificationSummary.genuine,
      flagged: analytics.verificationSummary.fake + analytics.verificationSummary.manual,
      txCount: sellerHistory.length,
    },
    products: [...sellerProducts]
      .sort((a, b) => b.id - a.id)
      .map((p) => ({
        id: p.id,
        brand: p.brand,
        productName: p.productName,
        modelName: p.modelName,
        serialNo: p.serialNo,
        image: p.originalImage,
        stage: p.currentOwnerType,
        canAssign: p.currentOwnerType === "Seller" && p.currentOwnerId === sellerId,
      })),
    consumers: store.consumers.map((c) => ({ id: c.id, name: c.fullName })),
    ledger: [...sellerHistory]
      .sort((a, b) => b.transferDate.localeCompare(a.transferDate))
      .map((h) => {
        const p = productById.get(h.productId);
        return {
          serialNo: p?.serialNo || "",
          product: p ? `${p.brand} · ${p.modelName}` : "",
          from: ownerName(h.fromOwnerType, h.fromOwnerId),
          to: ownerName(h.toOwnerType, h.toOwnerId),
          date: h.transferDate,
          hash: h.blockchainHash,
        };
      }),
  };

  res.render("seller_dashboard", {
    dash,
    pageTitle: "Seller Dashboard",
    pageHeading: "Overview",
    headingTitle: `${req.session.shop_name} Inventory`,
    headingSub: "Track assigned inventory and complete verified consumer handoffs.",
    tableTitle: "Assigned Inventory",
    totalProductsCount: sellerProducts.length,
    products: sellerProducts,
    kpis: [
      { label: "Total Handled", value: sellerProducts.length, foot: `${heldCount} currently in stock`, icon: "package" },
      { label: "Verified Genuine", value: analytics.verificationSummary.genuine, foot: "Consumer AI checks", icon: "check" },
      { label: "Flagged / Review", value: analytics.verificationSummary.fake + analytics.verificationSummary.manual, foot: "Requires inspection", icon: "alert" },
      { label: "Seller TXs", value: sellerHistory.length, foot: "Custody transfers", icon: "link" },
    ],
    ...analytics,
  });
});

app.get("/seller/assigned-products", (req: Request, res: Response) => {
  if (!req.session.seller_id) {
    return res.redirect("/seller/login");
  }

  const sellerId = req.session.seller_id;
  const historyIds = new Set(
    store.ownershipHistory
      .filter((h) => h.toOwnerType === "Seller" && h.toOwnerId === sellerId)
      .map((h) => h.productId)
  );
  const products = store.products
    .filter(
      (p) =>
        (p.currentOwnerType === "Seller" && p.currentOwnerId === sellerId) ||
        historyIds.has(p.id)
    )
    .sort((a, b) => b.id - a.id);

  res.render("seller_assigned_products", { products });
});

app.get("/seller/assign-consumer", (req: Request, res: Response) => {
  if (!req.session.seller_id) {
    return res.redirect("/seller/login");
  }

  const sellerId = req.session.seller_id;
  const products = store.products.filter(
    (p) => p.currentOwnerType === "Seller" && p.currentOwnerId === sellerId
  );

  res.render("seller_assign_consumer", {
    products,
    consumers: store.consumers,
  });
});

app.post("/seller/assign-product-consumer", (req: Request, res: Response) => {
  if (!req.session.seller_id) {
    return res.redirect("/seller/login");
  }

  const sellerId = req.session.seller_id;
  const productId = Number(req.body.product_id);
  const consumerId = Number(req.body.consumer_id);

  const product = store.products.find(
    (p) =>
      p.id === productId &&
      p.currentOwnerType === "Seller" &&
      p.currentOwnerId === sellerId
  );
  if (!product) {
    return res.status(404).send("Invalid Product");
  }

  const consumer = store.consumers.find((c) => c.id === consumerId);
  if (!consumer) {
    return res.status(404).send("Invalid Consumer");
  }

  product.currentOwnerType = "Consumer";
  product.currentOwnerId = consumerId;
  product.status = "Assigned to Consumer";

  const txHash = assignConsumerOnChain(product.serialNo, String(consumerId));
  store.addOwnershipRecord({
    productId: product.id,
    fromOwnerType: "Seller",
    fromOwnerId: sellerId,
    toOwnerType: "Consumer",
    toOwnerId: consumerId,
    blockchainHash: txHash,
  });

  const toast = encodeURIComponent(`Assigned #${product.serialNo} to buyer`);
  return redirectPreservingFallback(
    req,
    res,
    req.body.return_to === "dashboard"
      ? `/seller/dashboard?view=ledger&toast=${toast}`
      : `/seller/assigned-products?toast=${toast}`
  );
});

app.get("/seller/logout", (req: Request, res: Response) => {
  clearAuthSession(req, res, ["seller_id", "shop_name", "email"], "/seller/login");
});

// ==================== CONSUMER ROUTES ====================

app.get("/consumer/register", (_req: Request, res: Response) => {
  res.render("consumer_register", { error: null });
});

app.post("/consumer/register", (req: Request, res: Response) => {
  const fullName = String(req.body.full_name || "").trim();
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");

  if (!fullName || !email || !password) {
    return res
      .status(400)
      .render("consumer_register", { error: "All fields are required." });
  }

  const existing = store.consumers.find(
    (c) => c.email.toLowerCase() === email
  );
  if (existing) {
    return res
      .status(409)
      .render("consumer_register", { error: "Email already registered." });
  }

  store.addConsumer(fullName, email, password);
  return res.redirect("/consumer/login");
});

app.get("/consumer/login", (_req: Request, res: Response) => {
  res.render("consumer_login", { error: null });
});

app.post("/consumer/login", (req: Request, res: Response) => {
  const email = String(req.body.email || "").trim().toLowerCase();
  const password = String(req.body.password || "");

  const consumer = store.consumers.find(
    (c) => c.email.toLowerCase() === email && c.password === password
  );

  if (!consumer) {
    return res
      .status(401)
      .render("consumer_login", { error: "Invalid Email or Password" });
  }

  req.session.consumer_id = consumer.id;
  req.session.full_name = consumer.fullName;
  req.session.email = consumer.email;
  return redirectAfterAuth(req, res, "/consumer/dashboard");
});

app.get("/consumer/dashboard", (req: Request, res: Response) => {
  if (!req.session.consumer_id) {
    return res.redirect("/consumer/login");
  }

  const consumerId = req.session.consumer_id;
  const myProducts = store.products.filter(
    (p) => p.currentOwnerType === "Consumer" && p.currentOwnerId === consumerId
  );
  const myProductIds = new Set(myProducts.map((p) => p.id));
  const mySerials = new Set(myProducts.map((p) => p.serialNo));
  const myHistory = store.ownershipHistory.filter((h) => myProductIds.has(h.productId));
  const myVerifications = store.verifications.filter(
    (v) => v.checkedByConsumerId === consumerId || mySerials.has(v.serialNo)
  );

  const analytics = buildDashboardAnalytics(myProducts, myHistory, myVerifications);

  // Latest AI result per serial, newest check wins.
  const latestResult = new Map<string, string>();
  for (const v of [...myVerifications].sort((a, b) => a.checkedAt.localeCompare(b.checkedAt))) {
    latestResult.set(v.serialNo, v.finalResult);
  }
  const resultKey = (serial: string): "genuine" | "flagged" | "unchecked" => {
    const r = latestResult.get(serial);
    if (!r) return "unchecked";
    return r === "GENUINE PRODUCT" ? "genuine" : "flagged";
  };

  const dash = {
    fullName: req.session.full_name,
    stats: {
      owned: myProducts.length,
      genuine: analytics.verificationSummary.genuine,
      flagged: analytics.verificationSummary.fake + analytics.verificationSummary.manual,
      events: myHistory.length,
    },
    products: [...myProducts]
      .sort((a, b) => b.id - a.id)
      .map((p) => ({
        id: p.id,
        brand: p.brand,
        productName: p.productName,
        modelName: p.modelName,
        serialNo: p.serialNo,
        image: p.originalImage,
        stage: p.currentOwnerType,
        result: resultKey(p.serialNo),
      })),
  };

  res.render("consumer_dashboard", {
    dash,
    pageTitle: "Consumer Dashboard",
    pageHeading: "Overview",
    headingTitle: `Welcome, ${req.session.full_name}`,
    headingSub: "Review your owned products, ledger provenance, and AI verification reports.",
    tableTitle: "Owned Products",
    totalProductsCount: myProducts.length,
    products: myProducts,
    kpis: [
      { label: "Owned Products", value: myProducts.length, foot: "Assigned to account", icon: "package" },
      { label: "Verified Genuine", value: analytics.verificationSummary.genuine, foot: "Passed AI check", icon: "check" },
      { label: "Flagged / Review", value: analytics.verificationSummary.fake + analytics.verificationSummary.manual, foot: "Requires inspection", icon: "alert" },
      { label: "Ledger Events", value: myHistory.length, foot: "Recorded transfers", icon: "link" },
    ],
    ...analytics,
  });
});

app.get("/consumer/products", (req: Request, res: Response) => {
  if (!req.session.consumer_id) {
    return res.redirect("/consumer/login");
  }

  const products = store.products.filter(
    (p) =>
      p.currentOwnerType === "Consumer" &&
      p.currentOwnerId === req.session.consumer_id
  );
  res.render("consumer_products", { products });
});

app.get("/consumer/my-products", (req: Request, res: Response) => {
  if (!req.session.consumer_id) {
    return res.redirect("/consumer/login");
  }

  const products = store.products.filter(
    (p) =>
      p.currentOwnerType === "Consumer" &&
      p.currentOwnerId === req.session.consumer_id
  );
  res.render("consumer_my_products", { products });
});

app.get("/consumer/verify", (req: Request, res: Response) => {
  if (!req.session.consumer_id) {
    return res.redirect("/consumer/login");
  }
  res.render("consumer_verify");
});

app.get("/consumer/logout", (req: Request, res: Response) => {
  clearAuthSession(
    req,
    res,
    ["consumer_id", "full_name", "email"],
    "/consumer/login"
  );
});

// ==================== VERIFICATION ROUTES ====================

app.get("/verify", (_req: Request, res: Response) => {
  res.render("verify");
});

app.get("/verify/:serialNo", (req: Request, res: Response) => {
  const serialNo = String(req.params.serialNo);
  const product = store.products.find((p) => p.serialNo === serialNo);
  if (!product) {
    return res.status(404).send("Product Not Found");
  }

  const blockchain = verifyProductOnChain(serialNo);
  const loggedIn = Boolean(req.session.consumer_id);

  res.render("verify_product", {
    product,
    blockchain,
    logged_in: loggedIn,
  });
});

app.post(
  "/verify-image",
  consumerImageUpload.single("consumer_image"),
  async (req: Request, res: Response) => {
    if (!req.session.consumer_id) {
      return res.redirect("/consumer/login");
    }

    const consumerId = req.session.consumer_id;
    const serialNo = String(req.body.serial_no || "").trim();
    const uploadedFile = req.file;

    if (!uploadedFile) {
      return res.status(400).send("Please upload a product image.");
    }

    const product = store.products.find(
      (p) =>
        p.serialNo === serialNo &&
        p.currentOwnerType === "Consumer" &&
        p.currentOwnerId === consumerId
    );

    if (!product) {
      return res.status(404).send("Product Not Found");
    }

    const manufacturerImagePath = path.join(
      productImagesDir,
      product.originalImage
    );
    const { prediction, confidence } = await predictImage(uploadedFile.path);
    const similarity = await compareImages(
      manufacturerImagePath,
      uploadedFile.path
    );

    let finalResult:
      | "GENUINE PRODUCT"
      | "FAKE PRODUCT"
      | "MANUAL INSPECTION REQUIRED";
    if (similarity >= 85 && prediction === "genuine") {
      finalResult = "GENUINE PRODUCT";
      store.verificationStats.verifiedCount += 1;
    } else if (similarity < 50) {
      finalResult = "FAKE PRODUCT";
      store.verificationStats.fakeDetectedCount += 1;
    } else {
      finalResult = "MANUAL INSPECTION REQUIRED";
    }

    const confidencePercent = Number((confidence * 100).toFixed(2));
    const similarityPercent = Number(similarity.toFixed(2));
    store.addVerificationRecord({
      serialNo: product.serialNo,
      productName: product.productName,
      brand: product.brand,
      prediction,
      confidencePercent,
      similarityPercent,
      finalResult,
      checkedByConsumerId: consumerId,
    });
    const blockchainData = verifyProductOnChain(serialNo);

    const sellerRecord = store.sellers.find(
      (s) => String(s.id) === blockchainData.seller
    );
    const consumerRecord = store.consumers.find(
      (c) => String(c.id) === blockchainData.consumer
    );

    res.render("ai_verification", {
      product,
      uploaded_image: uploadedFile.filename,
      prediction,
      confidence,
      confidence_percent: confidencePercent,
      similarity,
      similarity_percent: similarityPercent,
      final_result: finalResult,
      blockchain_verified: blockchainData.exists,
      manufacturer_name: blockchainData.manufacturer,
      seller_name: sellerRecord
        ? `${sellerRecord.shopName} (ID #${sellerRecord.id})`
        : blockchainData.seller,
      consumer_name: consumerRecord
        ? `${consumerRecord.fullName} (ID #${consumerRecord.id})`
        : blockchainData.consumer,
    });
  }
);

// ==================== HISTORY & PRODUCT DETAILS ====================

app.get("/history", (_req: Request, res: Response) => {
  const records = store.ownershipHistory.map((h) => {
    const prod = store.products.find((p) => p.id === h.productId);
    return {
      ...h,
      serialNo: prod ? prod.serialNo : "N/A",
      brand: prod ? prod.brand : "Unknown",
      productName: prod ? prod.productName : "Unknown",
    };
  });
  res.render("history_index", { records });
});

// Custody trail for a serial as JSON (same data /history/:serialNo shows publicly).
app.get("/api/trail/:serialNo", (req: Request, res: Response) => {
  const serialNo = String(req.params.serialNo).trim().replace(/^#/, "");
  const product = store.products.find((p) => p.serialNo === serialNo);
  if (!product) {
    return res.status(404).json({ found: false });
  }
  const nameOf = (type: string, id: number): string => {
    if (type === "Manufacturer") return store.manufacturers.find((m) => m.id === id)?.companyName || "Manufacturer";
    if (type === "Seller") return store.sellers.find((s) => s.id === id)?.shopName || "Seller";
    return store.consumers.find((c) => c.id === id)?.fullName || "Consumer";
  };
  const history = store.ownershipHistory
    .filter((h) => h.productId === product.id)
    .sort((a, b) => a.transferDate.localeCompare(b.transferDate));
  const verbs: Record<string, string> = { Seller: "Received from manufacturer", Consumer: "Purchased" };
  res.json({
    found: true,
    serialNo: product.serialNo,
    product: `${product.brand} · ${product.modelName}`,
    trail: [
      { who: "Manufacturer", name: product.brand, what: "Registered", when: "" },
      ...history.map((h) => ({
        who: h.toOwnerType,
        name: nameOf(h.toOwnerType, h.toOwnerId),
        what: verbs[h.toOwnerType] || "Transferred",
        when: h.transferDate,
      })),
    ],
  });
});

app.get("/history/:serialNo", (req: Request, res: Response) => {
  const serialNo = String(req.params.serialNo);
  const product = store.products.find((p) => p.serialNo === serialNo);
  const history = product
    ? store.ownershipHistory.filter((h) => h.productId === product.id)
    : [];

  res.render("history", {
    history,
    serial_no: serialNo,
  });
});

app.get("/product/:productId", (req: Request, res: Response) => {
  const productId = Number(req.params.productId);
  const product = store.products.find((p) => p.id === productId);
  if (!product) {
    return res.status(404).send("Product Not Found");
  }
  res.render("product_details", { product });
});

app.get("/api/product/:productId", (req: Request, res: Response) => {
  const productId = Number(req.params.productId);
  const product = store.products.find((p) => p.id === productId);
  if (!product) {
    return res.status(404).json({ error: "Product not found" });
  }
  const history = store.ownershipHistory.filter((h) => h.productId === product.id);
  return res.json({ product, history });
});

// ==================== ADMIN ROUTES ====================

app.get("/admin/login", (_req: Request, res: Response) => {
  res.render("admin_login", { error: null });
});

app.post("/admin/login", (req: Request, res: Response) => {
  const username = String(req.body.username || "").trim();
  const password = String(req.body.password || "");

  if (username === "admin" && password === "admin123") {
    req.session.admin = true;
    return redirectAfterAuth(req, res, "/admin/dashboard");
  }

  return res
    .status(401)
    .render("admin_login", { error: "Invalid Credentials" });
});

app.get("/admin/dashboard", (req: Request, res: Response) => {
  if (!req.session.admin) {
    return res.redirect("/admin/login");
  }

  const analytics = buildDashboardAnalytics(
    store.products,
    store.ownershipHistory,
    store.verifications
  );

  res.render("admin_dashboard", {
    pageTitle: "Admin Dashboard",
    pageHeading: "Overview",
    headingTitle: "Platform Operations",
    headingSub: `${store.manufacturers.length} manufacturer · ${store.sellers.length} seller · ${store.consumers.length} consumers`,
    tableTitle: "All Registered Products",
    totalProductsCount: store.products.length,
    products: store.products,
    kpis: [
      { label: "Total Products", value: store.products.length, foot: `${store.manufacturers.length} manufacturers`, icon: "package" },
      { label: "Active Participants", value: store.manufacturers.length + store.sellers.length + store.consumers.length, foot: `${store.sellers.length} sellers · ${store.consumers.length} consumers`, icon: "users" },
      { label: "Verified Genuine", value: analytics.verificationSummary.genuine, foot: `${analytics.verificationSummary.fake} fake detected`, icon: "check" },
      { label: "Blockchain TXs", value: store.ownershipHistory.length, foot: "Ownership transfers", icon: "link" },
    ],
    ...analytics,
  });
});

app.get("/admin/logout", (req: Request, res: Response) => {
  clearAuthSession(req, res, ["admin"], "/admin/login");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`AI Fake Product Detection server listening on http://0.0.0.0:${PORT}`);
});
