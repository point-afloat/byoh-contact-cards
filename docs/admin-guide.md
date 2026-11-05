# Administrator guide

For the people who manage who may use the contact card importer. You do not need a developer for
any of this. Button and menu names are written in bold type, exactly as they appear in the app.

## Signing in for the first time

Whoever set up the app created the first administrator account with an email address and a
password. Open the app's address in your browser, enter them and sign in. Then open **Account**
and use **Change password** to choose a password only you know.

## Adding a colleague

1. Open **Users**.
2. Click **Invite a user**.
3. Type your colleague's email address and choose their role:
   - **Member**: can scan cards and send them to FundraisingBox.
   - **Administrator**: can do that and also manage users, like you.
4. Click **Create invitation link**.
5. Click **Copy link** and send the link to your colleague yourself, for example in a chat message
   or an email. **The app does not send emails.**
6. Click **Done**. Your colleague now appears in the list as *Invitation pending*.

The link works **once**, expires after **7 days**, and is shown **only now**. Copy it before you
close the window.

*What your colleague does:* opens the link, chooses a password and clicks **Set password and
sign in**. They are then signed in and can start scanning.

*If the link was lost or has expired:* on their card click **New invitation link**. The old link
stops working at once. *If you invited the wrong address:* click **Revoke invitation**; the
address can be invited again later.

## When someone leaves

Open **Users**, find the person and click **Deactivate**. The app asks you to confirm and names the
person. They are signed out immediately and cannot sign in again. Nothing is deleted, so you can
click **Reactivate** later and they can sign in with their old password.

## Changing someone's role

On their card use the **Role** menu. The change applies at their next click; they do not need to
sign in again. The app never lets you remove the last active administrator, so there is always
someone who can manage users. If you try, it tells you to make somebody else an administrator
first.

## Someone forgot their password

On their card click **Reset password link**, copy the link and send it to them. The link works once
and for **1 hour**. When they use it they choose a new password and are signed in, and every other
place they were signed in is signed out.

## Your own password

Open **Account** and use **Change password**. You need your current password. Any other devices
you were signed in on are signed out.

## Password rules

- At least **12 characters**. A short sentence of ordinary words is a good password.
- Not a very common password, and not the person's email address.

## If sign-in is paused

After **5 failed attempts** with the same email address within 10 minutes, sign-in for that address
is paused for a few minutes, even with the right password. Wait about 10 minutes and try again.
Other people are not affected.

## If no administrator can sign in any more

*This is for whoever runs the server.* Every administrator has lost access (forgotten passwords,
all accounts deactivated). Because the app has no email, it cannot send a reset itself. As the
last resort, you can start again from the first-administrator settings:

1. Set `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` on the service.
2. Stop the service and delete the database file `app.db` in the data folder (`/data` in Docker).
   **This removes all accounts.** Everyone has to be invited again.
3. Start the service. It creates the first administrator from those settings.
4. Sign in, change the password, and remove `INITIAL_ADMIN_PASSWORD` from the service settings.

The app ignores those two settings whenever any account exists, so leaving them set does no harm,
but the password should not stay in the settings longer than necessary.

## Newsletter and contact options

On the review page, under **Communication**, four boxes record what the person agreed to:
newsletter, contact by email, by phone and by post. None is ticked to begin with, and the app
never ticks one from the card: handing over a business card is not consent. Tick a box only when
the person told you so. A ticked box is written to the person's record in FundraisingBox; an unticked
box sends nothing, so FundraisingBox keeps whatever it has. The boxes are not remembered if you
reload the page.

If a send fails part way, the person already exists in FundraisingBox. Changing the boxes (or the
name or company) and sending again does not change that existing record; fix those in
FundraisingBox itself.

## What the app does not do

- It does not send emails (invitations and reset links are shared by you).
- It has no "forgot password" button for people who are signed out; an administrator issues a reset
  link instead.
- It has no two-step sign-in.
