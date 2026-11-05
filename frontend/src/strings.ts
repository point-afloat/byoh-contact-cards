// All user-facing text lives here so the UI language can be changed in one place.
export const strings = {
  appTitle: "Contact card importer",
  appTagline: "Scan a card, review it, send it to FundraisingBox.",
  steps: {
    upload: "Scan",
    review: "Review",
    done: "Done",
  },
  stepsLabel: "Progress",
  upload: {
    heading: "Scan a contact card",
    takePhoto: "Take a photo",
    chooseFile: "Choose a file",
    dropHint: "or drop a card image here",
    formatHint: "JPEG or PNG images only.",
    reading: "Reading the card…",
    wrongType: "Only JPEG and PNG images are accepted.",
  },
  review: {
    heading: "Review the contact",
    imageAlt: "The scanned contact card",
    intro:
      "Check the values against the card and correct anything that is wrong.",
    notFound: "Not found on the card",
    send: "Send to FundraisingBox",
    sections: {
      person: "Person",
      company: "Company",
      contact: "Contact details",
      address: "Address",
      notes: "Notes",
    },
    errors: {
      identity: "Enter a last name or a company.",
      email: "This is not a valid email address.",
    },
  },
  fields: {
    salutation: "Salutation",
    title: "Title",
    first_name: "First name",
    last_name: "Last name",
    company: "Company",
    position: "Position",
    email: "Email",
    phone: "Phone",
    mobile: "Mobile",
    website: "Website",
    street: "Street",
    postal_code: "Postal code",
    city: "City",
    country: "Country",
    notes: "Notes",
  },
  company: {
    legend: "FundraisingBox company",
    searching: "Searching FundraisingBox…",
    none: "Don't link, keep the company name as a note",
    link: (name: string, city?: string | null) =>
      city ? `Link to ${name} (${city})` : `Link to ${name}`,
    create: (name: string) =>
      `Create the company "${name}" in FundraisingBox and link the contact`,
    noMatch: "No matching company found in FundraisingBox.",
    searchFailed:
      "The company search is unavailable. You can still send without a company link.",
    companyOnlyNote:
      "There is no last name, so only the company will be created and no person.",
    mayExist: "A company with a similar name may already exist:",
  },
  send: {
    sending: "Sending…",
    failed:
      "Sending failed. Your entries are kept, so you can fix the problem and try again.",
  },
  mock: {
    label: "Mock mode",
    banner:
      "Mock mode: nothing is sent to FundraisingBox. Contacts you confirm are only shown on screen.",
  },
  done: {
    mockHeading: "Demo record created (not sent)",
    mockMessage: (id: string | null | undefined) =>
      `This contact was not sent to FundraisingBox. It was a demo record${id ? ` (ID ${id})` : ""}.`,
    mockPayloadSummary: "Show what would have been sent",
    heading: "Sent to FundraisingBox",
    person: (id: string | null | undefined) =>
      `The person was created${id ? ` (ID ${id})` : ""}.`,
    company: (id: string | null | undefined) =>
      `The company was created${id ? ` (ID ${id})` : ""}.`,
    next: "Scan next card",
  },
  nav: {
    scan: "Scan",
    users: "Users",
    account: "Account",
    signOut: "Sign out",
    mainLabel: "Main",
    signedInAs: "Signed in as",
  },
  auth: {
    loading: "Loading…",
    signInHeading: "Sign in",
    email: "Email",
    password: "Password",
    showPassword: "Show password",
    hidePassword: "Hide password",
    signIn: "Sign in",
    signingIn: "Signing in…",
    expiredHeading: "Your session expired",
    expiredText: "Please sign in again to continue. What you entered is kept.",
  },
  account: {
    heading: "Account",
    emailLabel: "Email",
    roleLabel: "Role",
    roles: { admin: "Administrator", member: "Member" } as Record<
      string,
      string
    >,
    changeHeading: "Change password",
    current: "Current password",
    next: "New password",
    confirm: "Repeat the new password",
    hint: "At least 12 characters.",
    submit: "Change password",
    saving: "Saving…",
    success: "Your password was changed. Other devices were signed out.",
    mismatch: "The two passwords do not match.",
    tooShort: "Use at least 12 characters.",
    required: "Enter your current password.",
  },
  invite: {
    checking: "Checking your link…",
    welcomeHeading: "Welcome. Choose a password",
    resetHeading: "Choose a new password",
    forEmail: "for",
    password: "Password",
    confirm: "Repeat the password",
    hint: "At least 12 characters.",
    submitInvite: "Set password and sign in",
    submitReset: "Save password and sign in",
    saving: "Saving…",
    invalidHeading: "This link is no longer valid",
    invalidText:
      "It may have been used already or may have expired. Ask an administrator for a new one.",
    toSignIn: "Go to sign in",
    retry: "Try again",
    mismatch: "The two passwords do not match.",
    tooShort: "Use at least 12 characters.",
  },
  users: {
    heading: "Users",
    intro:
      "Invite colleagues, and switch people off when they leave. Nobody needs a developer for this.",
    invite: "Invite a user",
    listLabel: "All users",
    loadFailed: "The users could not be loaded.",
    retry: "Try again",
    you: "(you)",
    role: "Role",
    roleFor: "for",
    roles: { admin: "Administrator", member: "Member" } as Record<
      string,
      string
    >,
    lastSignIn: "Last sign-in",
    neverSignedIn: "Has not signed in yet",
    status: {
      active: "Active",
      inactive: "Deactivated",
      pending: (until: string) =>
        `Invitation pending, link valid until ${until}`,
      expired: (since: string) => `Invitation expired on ${since}`,
    },
    actions: {
      deactivate: "Deactivate",
      reactivate: "Reactivate",
      resetLink: "Reset password link",
      newLink: "New invitation link",
      revoke: "Revoke invitation",
    },
    notices: {
      roleChanged: (email: string, role: string) => `${email} is now ${role}.`,
      deactivated: (email: string) =>
        `${email} was deactivated and signed out.`,
      reactivated: (email: string) => `${email} can sign in again.`,
      revoked: (email: string) => `The invitation for ${email} was withdrawn.`,
    },
    inviteDialog: {
      heading: "Invite a user",
      email: "Email address",
      role: "Role",
      submit: "Create invitation link",
      saving: "Creating…",
      cancel: "Cancel",
    },
    linkDialog: {
      inviteHeading: (email: string) => `Invitation link for ${email}`,
      resetHeading: (email: string) => `Password reset link for ${email}`,
      explanation: (email: string, until: string) =>
        `Send this link to ${email}. It works once and expires on ${until}. It is shown only now, so copy it before closing.`,
      linkLabel: "Link",
      copy: "Copy link",
      copied: "Link copied",
      done: "Done",
    },
    confirm: {
      deactivateHeading: (email: string) => `Deactivate ${email}?`,
      deactivateText:
        "They are signed out immediately and cannot sign in until you reactivate them.",
      revokeHeading: (email: string) => `Withdraw the invitation for ${email}?`,
      revokeText:
        "The link stops working and the address can be invited again later.",
      cancel: "Cancel",
    },
  },
  genericError: "Something went wrong. Please try again.",
  networkError:
    "The server could not be reached. Please check your connection and try again.",
} as const;
