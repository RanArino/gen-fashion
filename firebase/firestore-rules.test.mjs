// Firestore Security Rules unit tests for gen-fashion (M2-12).
//
// Run via:
//   firebase emulators:exec --only firestore --project gen-fashion-local "npm test"
//
// The Firebase rules-enforcing Firestore emulator is started by the wrapper
// command above; this file connects to it through @firebase/rules-unit-testing.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { test, after, before } from "node:test";
import assert from "node:assert/strict";

import {
  initializeTestEnvironment,
  assertSucceeds,
  assertFails,
} from "@firebase/rules-unit-testing";
import {
  doc,
  getDoc,
  getDocs,
  collection,
  setDoc,
  updateDoc,
  deleteDoc,
  serverTimestamp,
} from "firebase/firestore";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rulesPath = resolve(__dirname, "..", "firestore.rules");

let testEnv;

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: "gen-fashion-local",
    firestore: {
      rules: readFileSync(rulesPath, "utf8"),
      host: "127.0.0.1",
      port: 8080,
    },
  });
  // Seed a closet item via the admin (rule-bypassing) context so that the
  // owner-read and cross-user-read assertions have something to read.
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, "users/alice"), {
      displayName: "Alice",
      createdAt: serverTimestamp(),
    });
    await setDoc(doc(db, "users/alice/closet/item-1"), {
      status: "READY",
      imageUrl: "/alice/closet/item-1.jpg",
      category: "tops",
    });
  });
});

after(async () => {
  if (testEnv) await testEnv.cleanup();
});

test("owner can read their own users/{uid} profile", async () => {
  const alice = testEnv.authenticatedContext("alice").firestore();
  await assertSucceeds(getDoc(doc(alice, "users/alice")));
});

test("owner can get and list their own closet items", async () => {
  const alice = testEnv.authenticatedContext("alice").firestore();
  await assertSucceeds(getDoc(doc(alice, "users/alice/closet/item-1")));
  await assertSucceeds(getDocs(collection(alice, "users/alice/closet")));
});

test("another signed-in user cannot read someone else's profile", async () => {
  const bob = testEnv.authenticatedContext("bob").firestore();
  await assertFails(getDoc(doc(bob, "users/alice")));
});

test("another signed-in user cannot read someone else's closet item", async () => {
  const bob = testEnv.authenticatedContext("bob").firestore();
  await assertFails(getDoc(doc(bob, "users/alice/closet/item-1")));
});

test("owner cannot write to closet from the client (backend-only)", async () => {
  const alice = testEnv.authenticatedContext("alice").firestore();
  await assertFails(
    setDoc(doc(alice, "users/alice/closet/item-new"), { status: "READY" }),
  );
  await assertFails(
    updateDoc(doc(alice, "users/alice/closet/item-1"), { status: "ERROR" }),
  );
  await assertFails(deleteDoc(doc(alice, "users/alice/closet/item-1")));
});

test("owner can create their own users/{uid} profile (first-login bootstrap)", async () => {
  const charlie = testEnv.authenticatedContext("charlie").firestore();
  await assertSucceeds(
    setDoc(doc(charlie, "users/charlie"), {
      displayName: "Charlie",
      createdAt: serverTimestamp(),
    }),
  );
});

test("unauthenticated requests are denied", async () => {
  const anon = testEnv.unauthenticatedContext().firestore();
  await assertFails(getDoc(doc(anon, "users/alice")));
  await assertFails(getDoc(doc(anon, "users/alice/closet/item-1")));
});
