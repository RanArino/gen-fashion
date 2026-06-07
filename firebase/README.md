# Firestore Security Rules unit tests (M2-12)

This package proves the rule set in `../firestore.rules` allows and denies the
right paths. It runs against the **rule-enforcing** Firebase Firestore emulator
(the gcloud Firestore emulator the dev `docker-compose.yml` uses does not
enforce rules — see the M2 frontend ExecPlan Decision Log).

## Prerequisites

- Node 20+
- `firebase-tools` installed (`npm install -g firebase-tools`)
- A Java 11+ JRE (the Firebase Firestore emulator requires it)

## Run

From this directory:

```bash
npm install
firebase emulators:exec --only firestore --project gen-fashion-local "npm test"
```

`firebase emulators:exec` spins up the rule-enforcing Firestore emulator just
for the test, then tears it down. The wrapper picks up `../firebase.json` for
the emulator port and the rules path.
