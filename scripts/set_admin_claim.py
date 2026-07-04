"""
One-off utility to grant (or revoke) the `admin` custom claim on a Firebase
user. Run this after a user has signed in at least once (Firebase must know
about the account).

Usage:
    python scripts/set_admin_claim.py user@example.com --grant
    python scripts/set_admin_claim.py user@example.com --revoke

Requires Application Default Credentials with permission to manage the
Firebase/Identity Platform project (e.g. `gcloud auth application-default login`
with a Firebase Admin / Owner role), or GOOGLE_APPLICATION_CREDENTIALS pointing
at a service account key with the "Firebase Authentication Admin" role.

Note: the user must sign out and back in (or force-refresh their ID token)
before the new claim takes effect in the app.
"""
import argparse
import sys

import firebase_admin
from firebase_admin import auth, credentials


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant/revoke the admin custom claim")
    parser.add_argument("email", help="Email address of the Firebase user")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--grant", action="store_true", help="Grant admin privileges")
    group.add_argument("--revoke", action="store_true", help="Revoke admin privileges")
    args = parser.parse_args()

    firebase_admin.initialize_app(credentials.ApplicationDefault())

    try:
        user = auth.get_user_by_email(args.email)
    except auth.UserNotFoundError:
        print(f"No Firebase user found for {args.email}. They must sign in at least once first.")
        sys.exit(1)

    claims = user.custom_claims or {}
    claims["admin"] = bool(args.grant)
    auth.set_custom_user_claims(user.uid, claims)

    action = "granted" if args.grant else "revoked"
    print(f"Admin privileges {action} for {args.email} (uid={user.uid}).")
    print("They must sign out/in (or refresh their ID token) for this to take effect.")


if __name__ == "__main__":
    main()
