# QuickTop — airtime via USSD

Django app behind a Brilio USSD code. Subscribers buy airtime, pay with an
M-Pesa STK push (Safaricom Daraja), and the airtime is sent with Statum.

```
Welcome to QuickTop
1. Buy Airtime        -> my number / other number -> amount -> confirm -> M-Pesa prompt
2. Buy Data           -> Safaricom / Airtel / MTN placeholder bundles (coming soon)
3. Pay Utilities      -> ZUKU, KPLC prepaid/postpaid (coming soon)
4. Insurance          -> Motor, Health, Personal Accident, Funeral (coming soon)
```

`0` goes back a screen and `00` returns to the main menu. If the input is invalid, the same screen is shown again with an error.

## How a purchase flows

1. **Brilio → `POST /ussd/callback/`.** The subscriber confirms, then the app creates an `MpesaPayment` and an
   `AirtimePurchase` (status `awaiting_payment`) and replies `END`.
2. About 3 seconds later (`STK_PUSH_DELAY_SECONDS`), once the USSD screen has closed, the app sends the STK push.
3. **Daraja → `POST /payments/mpesa/callback/`.** On success the purchase becomes `paid`
   and the app calls Statum (status `sending`).
4. **Statum → `POST /airtime/statum/callback/`.** The purchase becomes `delivered`, or `failed`.

A purchase in `failed` status means the customer paid but got no airtime, so **they are owed a refund**.
Filter for these in Django admin under Airtime purchases.

## Local development

```bash
python -m venv venv && venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env                              # fill in keys
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
python manage.py test
```

Daraja and Statum both need public HTTPS callback URLs. To test callbacks locally, expose port 8000 with a tunnel
(ngrok or cloudflared) and set `PUBLIC_BASE_URL` to the tunnel's URL.

## Deploying on Railway

1. Push this repo to GitHub. In the Railway project that holds the Postgres service, click **New → GitHub Repo**.
2. In the web service, go to **Settings → Networking → Generate Domain**.
3. Set these service variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `DJANGO_SECRET_KEY` | long random string |
| `BRILIO_CALLBACK_SECRETS` | the channel's callback secret from Brilio |
| `MPESA_ENV` | `sandbox` or `production` |
| `MPESA_CONSUMER_KEY` / `MPESA_CONSUMER_SECRET` / `MPESA_PASSKEY` / `MPESA_SHORTCODE` | from Daraja |
| `MPESA_TRANSACTION_TYPE` | `CustomerPayBillOnline` (paybill) or `CustomerBuyGoodsOnline` (till, and also set `MPESA_PARTY_B` to the till number) |
| `STATUM_CONSUMER_KEY` / `STATUM_CONSUMER_SECRET` | from the Statum dashboard |

You don't need to set `PUBLIC_BASE_URL` or `ALLOWED_HOSTS` on Railway. Both are read from `RAILWAY_PUBLIC_DOMAIN`.
`railway.json` runs `collectstatic` at build time and `migrate` each time the app starts. `/health/` checks the database too, so a deploy with missing tables fails instead of going live.

4. Create an admin user: run `railway ssh` (pick the app service), then `python manage.py createsuperuser`.
5. Register the callback URLs:
   - **Brilio** (USSD Sandbox → Create Channel, or your live code): `https://<domain>/ussd/callback/`
   - **Statum** dashboard callback URL: `https://<domain>/airtime/statum/callback/`
   - Daraja needs no registration, because the app sends the callback URL with each STK push.

## Testing with the Brilio simulator

Open the developer portal and go to **USSD Sandbox → Simulator**. Enter a Kenyan number, dial your channel code, and
step through the menus. The **Sessions** page shows each request and reply. An `HTTP 401` there means the
`BRILIO_CALLBACK_SECRETS` value doesn't match the channel's test secret.

## Dashboard

Staff-only console at `/dashboard/`. Log in with a Django admin account. It shows collections, deliveries,
refunds due, the conversion funnel, and searchable lists of purchases, M-Pesa payments, USSD sessions and
customers. Use **Retry airtime** on a failed, paid purchase once your Statum balance has been topped up.

The styles are Tailwind, compiled into `dashboard/static/dashboard/app.css`, which is committed so Railway
doesn't need Node. After you change a dashboard template, rebuild the CSS:

```bash
npm i --no-save --no-package-lock tailwindcss@4.1.11 @tailwindcss/cli@4.1.11
npx @tailwindcss/cli -i dashboard/assets/tailwind.css -o dashboard/static/dashboard/app.css --minify
```

Don't add a `package.json`. Railway would then try to build the app as a Node project.
