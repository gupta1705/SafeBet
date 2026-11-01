# SafeBet

**Adversarial pre-trade risk intelligence for ERC-20 and Stellar assets.**

SafeBet takes one contract address and, in a few seconds, puts together a forensic risk profile of the token. It reads raw EVM storage, replays the buy → approve → sell lifecycle against a forked view of live chain state, statically analyses the verified Solidity source, models liquidity collapse under constant-product AMM math, and profiles the deployer's history. All of this collapses into one pessimistic, confidence-capped **Trust Score**, plus a plain-English verdict that says what the catch is.

It is built to answer one question before you put money in: *can I get out?*

---

## How it works

SafeBet runs three independent analysis modules at the same time over a shared evidence graph. Each module both produces and consumes findings, so a signal from one module can raise or lower confidence in another (for example, an upgradeable proxy with an EOA admin makes a "clean" simulation less trustworthy).

```
                         ┌──────────────────────────┐
   token address  ──────▶│   Evidence Acquisition   │
                         │  chain state · bytecode  │
                         │  verified source · depth │
                         └────────────┬─────────────┘
                                      │  async fan-out
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
 ┌─────────────────┐       ┌─────────────────────┐      ┌──────────────────┐
 │ Module 1        │       │ Module 2            │      │ Module 3         │
 │ Contract Control│◀─────▶│ Trap Detection      │◀────▶│ Liquidity        │
 │                 │       │                     │      │ Collapse         │
 │ • EIP-1967 slot │       │ • State-override    │      │ • x·y=k dump     │
 │   introspection │       │   sell simulation   │      │   modelling      │
 │ • Admin typing  │       │ • 13-rule trap      │      │ • LP burn/lock   │
 │   (EOA/Safe/    │       │   engine            │      │   verification   │
 │   Timelock)     │       │ • Revert taxonomy   │      │ • Holder concen- │
 │ • Ownership &   │       │ • Tax inference     │      │   tration        │
 │   mint authority│       │                     │      │                  │
 └────────┬────────┘       └──────────┬──────────┘      └────────┬─────────┘
          └───────────────────────────┼──────────────────────────┘
                                      ▼
                     ┌────────────────────────────────┐
                     │ Pessimistic Scoring + Verdict  │
                     │ penalty table · confidence cap │
                     │ entity priors · LLM narrative  │
                     └────────────────────────────────┘
```

### 1. Contract Control analysis

- **Proxy introspection.** Reads the EIP-1967 implementation, beacon and admin storage slots directly (`keccak256("eip1967.proxy.*") - 1`) to tell whether the logic behind a token can be swapped out from under its holders.
- **Admin classification.** Resolves the proxy admin and checks its bytecode to classify it as an externally owned account, a Gnosis Safe multisig, or a Timelock controller. An instant single-key upgrade and a 48-hour governed upgrade carry very different risks, and SafeBet scores them differently.
- **Authority surface.** Ownership renouncement, mint capability, blacklist/freeze powers and role-based access control are extracted and cross-referenced with the source scan.

### 2. Trap Detection (honeypot engine)

- **Zero-cost sell simulation.** SafeBet builds synthetic token balances and router allowances by computing the exact `keccak256(abi.encode(holder, slot))` storage positions, then injects them through `eth_call` **state overrides**. The full buy → approve → sell path runs against live pool reserves without broadcasting a transaction, spending gas or holding the token.
- **Revert taxonomy.** Raw EVM revert data is decoded and classified into categories such as *transfer blocked*, *trading disabled*, *blacklisted*, *max-tx exceeded* and *cooldown active*. Each category comes with a consequence sentence a non-technical user can act on.
- **Effective tax inference.** Buy and sell tax are worked out empirically by comparing `getAmountsOut` quotes with simulated output, so tokens that hide or misreport their fees are caught.
- **13-rule trap engine.** Deterministic rules combine simulation, source and on-chain evidence to flag honeypots, proxy traps, tax flips, confiscatory tax, trading kill switches, wallet freezes, soft-honeypot limits, cooldowns, destructive admin functions, mint risk, thin markets, chain mismatch and unverifiable source.
- **Static source analysis.** A pattern engine scans verified Solidity for owner-mutable fee setters, `delegatecall` surfaces, trading toggles, blacklist mappings and governance primitives. It also separates professional architecture (OpenZeppelin, timelocks, multisig) from rug-pull patterns.

### 3. Liquidity Collapse modelling

- **Constant-product dump simulation.** Using Uniswap V2 invariant math (`x · y = k`, 0.3% swap fee included), SafeBet models what happens to the price, and to *your* position, if the top holders sell into the pool, one at a time and together.
- **LP lock verification.** LP token balances are checked on-chain at known burn addresses and at locker contracts (Unicrypt, PinkLock, Team Finance) to work out what share of liquidity is actually locked. Front-end labels are not trusted.
- **Holder concentration.** The supply distribution is rebuilt and normalised against decimals-aware total supply.
- **Deployer forensics.** The deploying wallet's contract-creation history is profiled to find serial deployers whose earlier tokens are now dead.

### 4. Scoring and verdict

- **Pessimistic by design.** Every token starts at 100 and loses points both for each finding *and* for each check that could not be completed. If something can't be verified, SafeBet assumes it isn't safe.
- **Confidence capping.** The final score is capped by data confidence, so a token with missing evidence can never land in the "safe" band.
- **Entity priors.** Well-known regulated issuers (USDC, USDT, DAI, WETH, LINK and others) are recognised, so compliance-driven admin powers aren't confused with malicious intent.
- **Narrative layer.** A single structured LLM pass turns the evidence into a verdict, a "the catch" summary and plain-language explanations for each flag. The LLM only explains. All detection and scoring is deterministic.

### Stellar support

For Stellar assets, SafeBet inspects the issuer account's native authorisation flags (`auth_required`, `auth_revocable`, `auth_immutable`, `auth_clawback`) and flags issuers who can freeze or claw back holder balances and are still free to change that behaviour later.

---

## Tech stack

| Layer    | Technology |
|----------|------------|
| Backend  | Python · FastAPI · asyncio · web3.py · eth-abi · Pydantic v2 |
| Chain    | Ethereum JSON-RPC (state overrides, raw storage reads) · Stellar Horizon via `stellar-sdk` |
| Frontend | React 18 · Vite · React Router · Chart.js |
| AI       | Anthropic Claude (narrative generation only) |

## Project structure

```
safebet/
├── backend/
│   ├── analyzers/      # trap rules, scoring, source scanning, dump math, deployer profiling
│   ├── blockchain/     # RPC client, proxy detection, sell simulation, Stellar client
│   ├── services/       # data-layer adapters, LP verification, AI narrative engine
│   ├── routers/        # /api/scan and /api/stellar endpoints
│   └── schemas/        # typed findings, severities, verdicts
└── frontend/
    └── src/            # landing, live scan and report views
```

## Getting started

### Backend

```bash
cd safebet/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd safebet/frontend
npm install
npm run dev
```

Open `http://localhost:5173`, paste a token address, and run a scan.

## Disclaimer

SafeBet is a risk-analysis tool, not financial advice. A high Trust Score means SafeBet didn't find known trap patterns. It is not a guarantee of safety. Always do your own research.
