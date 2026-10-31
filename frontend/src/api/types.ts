// Named aliases over the generated OpenAPI types. Never edit schema.d.ts by hand:
// regenerate it with `npm run api:generate` after changing the backend models.
import type { components } from "./schema";

export type Contact = components["schemas"]["Contact"];
export type SessionOut = components["schemas"]["SessionOut"];
export type SendRequest = components["schemas"]["SendRequest"];
export type CompanyChoice = components["schemas"]["CompanyChoice"];
export type CompanyMatch = components["schemas"]["CompanyMatch"];

export const CONTACT_FIELD_NAMES = [
  "salutation",
  "title",
  "first_name",
  "last_name",
  "company",
  "position",
  "email",
  "phone",
  "mobile",
  "street",
  "postal_code",
  "city",
  "country",
  "website",
  "notes",
] as const satisfies readonly (keyof Contact)[];
