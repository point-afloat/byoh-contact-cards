# Demo day plan: Sliplane 48-hour demo server

Goal: on the day of the appointment with the NGO, run the app on Sliplane's free demo server and
show the whole flow. You use it, the NGO watches.

**The constraint that shapes everything:** per [Sliplane's pricing FAQ](https://sliplane.io/pricing)
a demo server "will be automatically deleted after 48 hours". The 48-hour clock starts when you
create the demo server, so **do all preparation first**, with the clock not running, and create the
server only shortly before the appointment. Adding a payment method *before* the 48 hours are up
turns it into a paid server that keeps its services and data (the cheapest, Starter, is listed at
9 € per month excluding VAT).

Not stated in Sliplane's documentation, so check them on the day: whether a demo server can have a
volume, its size limits, which region it uses, whether a payment method is needed to create it, and
whether the service gets an HTTPS address. The plan has a fallback if any of these fail.

## 1. Decisions to make first

| Decision | Options | Recommendation |
|---|---|---|
| FundraisingBox during the demo | Mock it, a test account, or the real account | **Mock it** (decided). This needs the `add-fundraisingbox-mock-mode` change to be built first. Until it is, the app has no dry-run mode, and every send would create a real person (and possibly a company) in whatever account the token belongs to. In mock mode nothing is sent, no token is needed, and the app says so on every page. |
| Cards for the demo | The NGO's real cards, or your own test cards | Your own: 3 printed and 2 handwritten cards with invented people. Card images go to Mistral's hosted API, so avoid real donors' data until the NGO has agreed to that. |
| Model | Which cheap Mistral vision model | Decided by the 10-card test in step 2 below (task 2.4 of `build-contact-card-importer`). |
| After the 48 hours | Let it expire, or keep it | Decide by about hour 36 (see section 4). |

## 2. Before the day (the Sliplane clock is not running)

Allow about half a day, spread over several days.

1. **Commit and push the code (about 30 min).** The repository has many uncommitted files and no
   GitHub remote. Review and commit them, create a **private** GitHub repository, add it as
   `origin` and push `main`. Sliplane's Git source is GitHub only.
2. **Choose the model (about 1 hour).** Put your Mistral key in a local `.env` (copy `.env.example`;
   it is git-ignored), run `docker compose up --build`, and scan 10 cards (printed and handwritten)
   with the cheapest candidate vision models. Note cost and accuracy per field. Set `LLM_MODEL`.
3. **Try every send case in mock mode (about 30 min).** Set `FUNDRAISINGBOX_MODE=mock` and send
   one card for each case: person only, person linked to an example company, person with a new
   company, and a company-only card. The done screen shows what would have been sent. Real
   FundraisingBox is not tried yet (task 3.4 stays open), so tell the NGO the connection is shown
   with a stand-in.
4. **Rehearse on your own machine (about 1 hour).** Run `bash scripts/smoke-container.sh`
   (builds the image and runs 34 checks). Then open `http://<your-laptop-address>:8080` on your phone
   on the same Wi-Fi and scan a card with the camera. For plain http locally, set
   `AUTH_COOKIE_SECURE=false` in `.env`. Check Android and iPhone if you can, and whether iPhone photos
   work (task 6.3).
5. **Prepare the secrets.** Keep these in a password manager, never in the repository or in chat:
   `LLM_API_KEY`, `FUNDRAISINGBOX_APITOKEN`, and a strong `INITIAL_ADMIN_PASSWORD` (at least 12
   characters). Write down the admin email too.
6. **Prepare Sliplane.** Create the account and install Sliplane's GitHub app on the private
   repository, if Sliplane lets you do that before a server exists. Do **not** create the demo server
   yet.
7. **Plan B.** Make sure the local setup from step 4 works from a clean start, on a charged laptop.

The day before: re-read the runbook ([deploying to Sliplane](deployment-sliplane.md)) and the
administrator guide ([admin guide](admin-guide.md)), and charge your phone.

## 3. On the day

**About 1.5 hours before the appointment, create the demo server** (this starts the 48 hours).

| Step | What to do | Done when |
|---|---|---|
| 1 | Create the demo server, then **Deploy Service** from the GitHub repository (Dockerfile `/Dockerfile`, context `/`). | The build starts. If the demo server has no volume option, skip step 3 and note that accounts will not survive a redeploy. |
| 2 | Set the environment variables from the runbook, with the secret ones marked **secret**: `LLM_MODEL`, `LLM_API_KEY`, `FUNDRAISINGBOX_MODE=mock` (no FundraisingBox token needed), `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `SLIPLANE_USER_ID=10001`, `SLIPLANE_GROUP_ID=10001`. Leave `TRUSTED_PROXY` unset until step 9 passes. | All set. |
| 3 | Attach a volume at `/data`. Set the health check route to `/api/health`. | Redeploy finishes. |
| 4 | Open the service address. Without signing in you must see only the sign-in page, and `https://<address>/api/auth/me` must answer `401`. | Confirmed. |
| 5 | Sign in as the first administrator. Open **Account** and change the password. Then **remove `INITIAL_ADMIN_PASSWORD`** from the service and redeploy. | Signed in with the new password after the redeploy. |
| 6 | Open **Users** and invite a second person (your own other address). Open the link on a second device and choose a password. | The second person is signed in. |
| 7 | On your phone, scan one test card with the camera and send it. | The page shows the demo notice, and the done screen says nothing was sent and shows the data that would have been sent. |
| 8 | Redeploy once. | Both users can still sign in (this proves the volume works). |
| 9 | Check that sign-in throttling sees real visitor addresses (needs the `harden-login-and-requests` change). Use a **made-up email**, never a real user's: run `for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<address>/api/auth/login -H 'Content-Type: application/json' -H "X-Forwarded-For: 10.0.0.$i" -d '{"email":"probe@example.invalid","password":"wrong-password-123"}'; done` once with `TRUSTED_PROXY=true`. Then send the same request from your phone on mobile data (not Wi-Fi). | The laptop shows `401` five times, then `429`, and the phone gets `401`, not `429`. If the laptop never reaches `429` the proxy passes forged addresses through. If the phone also gets `429` the proxy adds more than one hop. In either case set `TRUSTED_PROXY` back to `false`. To repeat the test, wait 10 minutes or use another made-up email. |

If steps 1 to 9 take longer than 45 minutes, switch to Plan B for the appointment and carry on
debugging afterwards.

**Demo script (about 15 minutes):** sign in; scan a printed card and a handwritten one with the
phone; show the review screen and fix one field; pick an example company; send; show the "would have been sent" data on the done screen; open **Users**,
invite a colleague and show that the link is one-time; deactivate that colleague and show that they
are signed out at once; explain what stays on the server (accounts only, never cards).

## 4. Within the 48 hours

- **About hour 24:** look at the deployment logs. Lines starting `Startup problem:` name any
  configuration problem. Check that the health check is green.
- **By about hour 36, decide:** let it expire, or add a payment method to keep it. If you keep it,
  review it again before real data goes in: the data-protection agreement with the NGO and Mistral,
  the region, a custom domain, and the open tasks (accessibility pass, README).
- **If you let it expire,** nothing needs exporting: card images are never stored, and accounts can
  be created again from the first-administrator settings.

## 5. If something goes wrong

| Symptom | Likely cause | What to do |
|---|---|---|
| Health check stays red | A setting is missing | Read the log for `Startup problem:`. Common: no `INITIAL_ADMIN_*` on an empty database, `LLM_MODEL` empty, `FUNDRAISINGBOX_APITOKEN` missing. |
| Log says `/data` is not writable | Volume owned by another user | Check `SLIPLANE_USER_ID` and `SLIPLANE_GROUP_ID` are both `10001`. |
| Sign-in works but you are signed out immediately | Cookie not accepted | Check you open the `https` address, and that `AUTH_COOKIE_SECURE` is not `false`. |
| Scan fails with "could not be reached" or "rejected the API key" | Model endpoint or key | Check `LLM_API_KEY` and `LLM_BASE_URL`; try again; use Plan B for the demo. |
| Send fails | Over-long notes or a validation message | Read the message shown. In mock mode no FundraisingBox error can occur. |
| Everything is broken 30 minutes before | Anything | Plan B: run it on your laptop with `docker compose up` and show that. |

## 6. After the demo

1. Delete the demo server (or let it expire) and remove the Sliplane GitHub app's access if you no
   longer need it.
2. Revoke or rotate the Mistral key if it was shared or pasted anywhere. Mock records disappear with
   the server, so there is nothing to delete in FundraisingBox.
3. Tick the matching tasks: 4.2 to 4.4 of `add-sliplane-docker-deployment`, 5.2 of
   `add-user-accounts` and 6.3 of `build-contact-card-importer`, and note what you learned in the
   runbook.

## What this plan assumes but could not be checked from here

- That a demo server accepts GitHub deploys, volumes and a health check route.
- That the service address is served over HTTPS.
- That Sliplane's proxy adds the visitor's address as the last `X-Forwarded-For` entry and adds
  exactly one hop (step 9 checks it).
- That `SLIPLANE_USER_ID` and `SLIPLANE_GROUP_ID` make the volume writable for the container user.
- That the chosen Mistral model accepts structured output with an image (task 2.4 settles it).
- That the mock-mode change is built and verified before the day (it is planned, not built yet).
- That the real FundraisingBox connection works: it is deliberately not tested in this demo, so
  before real use set `FUNDRAISINGBOX_MODE=live`, add the token and run task 3.4.
