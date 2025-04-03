from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountLines

client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")

# Define accounts
kik_issuer = "rKacR1Mm32ve7wPsemwr52S9187StFTnWy"
kik_account_a = 'rN34Ss5moqYKYB8v3c8B3LyNwSUTCUVSaV'
kik_account_a_seed = 'sEdVXYoiSjQgs1CuvbFD9Biqy1ZyMnP'
kik_account_b = 'rfQJe2GiUhQ5BZVAUtj4JV39t2aq7xKv3J'
kik_account_b_seed = 'sEdTwrJCwZyJ4UDm4G16eAyRgMeL2pa'

lam_issuer = 'r9N6k8vWCekj2F3a2iNuAGUEbmdr6d7ty4'
lam_account_a = 'r985UBS7s7K9ytQyVkN7Hovkfb62KZVHfx'
lam_account_a_seed = 'sEdSMRumkDMgmRvsUXWGZ2XkvhMFEsT'
lam_account_b = 'rpA21iTZxerFzz7K9WgG5Ltr5CYCTfhdVT'
lam_account_b_seed = 'sEdT41wX5MhZRSBGW4jVDGzmxXt7F43'

tst_issuer = 'rEKBMamgBVqeqYNsHS2zstJT2id58GdYUM'
tst_account_a = 'rpAgpvztaPKYPwiTrtmeJhZnK5TebaQd9E'
tst_account_a_seed = 'sEd7jXsx3C6m2NSUPcFo1vTDv995jcx'
tst_account_b = 'rKR8Z8rYx7ESxJHytaf5s8rGDpJH8mygG4'
tst_account_b_seed = 'sEdV899ZkEGGNPmWVzg4rRG8mhCgJEZ'

bot_account = "rHDapemJvUwifB4vStymwXPPvsXjJSC7mq"
bot_seed = 'sEdT4FYXxxjfvy58595ozPFXqNKSNZL'

rob_issuer = "rPr9iQF4dXTrQwGQ8nJkGZWKymzTa1iCcr"
rob_account_seed = "sEd7o8hd22UYQ3qP23ZiPwaMdbVLGr5"

kik_currency = "KIK"
lam_currency = "LAM"
tst_currency = "TST"
rob_currency = "ROB"


def check_trust_line(account, label, issuer, currency):
    try:
        request = AccountLines(
            account=account,
            ledger_index="validated"
        )
        response = client.request(request).result
        lines = response.get("lines", [])

        # Look for trust line to the issuer
        for line in lines:
            if line["currency"] == currency and line["account"] == issuer:
                print(f"{label}:")
                print(f"  Trust Line Found - Currency: {line['currency']}, Issuer: {line['account']}")
                print(f"  Limit: {line['limit']} {currency}")
                print(f"  Balance: {line['balance']} {currency}")
                return True
        print(f"{label}: No {currency} trust line to issuer {issuer} found.")
        return False
    except Exception as e:
        print(f"Error checking trust line for {label}: {str(e)}")
        return False


# Check all accounts
print("Checking trust lines...\n")
bot_to_kik_ok = check_trust_line(bot_account, "Bot Account KIK", kik_issuer, kik_currency)
bot_to_lam_ok = check_trust_line(bot_account, "Bot Account LAM", lam_issuer, lam_currency)
bot_to_tst_ok = check_trust_line(bot_account, "Bot Account TST", tst_issuer, tst_currency)

kik_account_a_ok = check_trust_line(kik_account_a, "Account A KIK", kik_issuer, kik_currency)
kik_account_b_ok = check_trust_line(kik_account_b, "Account B KIK", kik_issuer, kik_currency)

lam_account_a_ok = check_trust_line(lam_account_a, "Account A LAM", lam_issuer, lam_currency)
lam_account_b_ok = check_trust_line(lam_account_b, "Account B LAM", lam_issuer, lam_currency)

tst_account_a_ok = check_trust_line(tst_account_a, "Account A TST", tst_issuer, tst_currency)
tst_account_b_ok = check_trust_line(tst_account_b, "Account B TST", tst_issuer, tst_currency)

rob_account_ok = check_trust_line(bot_account, "ROB Account", rob_issuer, rob_currency)

print("\nSummary:")
print(f"Bot Account Trust Line KIK OK: {bot_to_kik_ok} LAM OK: {bot_to_lam_ok} TST OK: {bot_to_tst_ok} ROB OK: {rob_account_ok}")
print(f"Account A Trust Line KIK OK: {kik_account_a_ok} Account B Trust Line KIK OK: {kik_account_b_ok}")
print(f"Account A Trust Line LAM OK: {lam_account_a_ok} Account B Trust Line LAM OK: {lam_account_b_ok}")
print(f"Account A Trust Line TST OK: {tst_account_a_ok} Account B Trust Line TST OK: {tst_account_b_ok}")

# if bot_ok and account_a_ok and account_b_ok:
if bot_to_kik_ok and bot_to_lam_ok and bot_to_tst_ok and rob_account_ok:
    print("\nAll trust lines for the bot are set up correctly!")
else:
    print("\nOne or more trust lines are missing or misconfigured for the bot.")

if kik_account_a_ok and kik_account_b_ok:
    print("\nAll trust lines for the KIK are set up correctly!")
else:
    print("\nOne or more trust lines are missing or misconfigured for KIK.")

if lam_account_a_ok and lam_account_b_ok:
    print("\nAll trust lines for the LAM are set up correctly!")
else:
    print("\nOne or more trust lines are missing or misconfigured for LAM.")

if tst_account_a_ok and tst_account_b_ok:
    print("\nAll trust lines for the TST are set up correctly!")
else:
    print("\nOne or more trust lines are missing or misconfigured for TST.")