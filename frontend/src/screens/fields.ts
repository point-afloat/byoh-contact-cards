import { z } from "zod";
import { CONTACT_FIELD_NAMES, type Contact } from "@/api/types";
import { strings } from "@/strings";

export type FieldName = (typeof CONTACT_FIELD_NAMES)[number];

export type FieldConfig = {
  name: FieldName;
  type: "text" | "email" | "tel" | "url" | "textarea";
  autoComplete?: string;
  /** Suggested values shown by the browser while typing (the server maps aliases). */
  suggestions?: string[];
};

export type SectionConfig = { id: keyof typeof strings.review.sections; fields: FieldConfig[] };

// One list drives the form: add a backend Contact field, add it here.
export const SECTIONS: SectionConfig[] = [
  {
    id: "person",
    fields: [
      {
        name: "salutation",
        type: "text",
        autoComplete: "honorific-prefix",
        suggestions: ["Mr.", "Mrs.", "diverse", "couple", "family"],
      },
      { name: "title", type: "text", autoComplete: "honorific-prefix" },
      { name: "first_name", type: "text", autoComplete: "given-name" },
      { name: "last_name", type: "text", autoComplete: "family-name" },
    ],
  },
  {
    id: "company",
    fields: [
      { name: "company", type: "text", autoComplete: "organization" },
      { name: "position", type: "text", autoComplete: "organization-title" },
    ],
  },
  {
    id: "contact",
    fields: [
      { name: "email", type: "email", autoComplete: "email" },
      { name: "phone", type: "tel", autoComplete: "tel" },
      { name: "mobile", type: "tel", autoComplete: "tel" },
      { name: "website", type: "url", autoComplete: "url" },
    ],
  },
  {
    id: "address",
    fields: [
      { name: "street", type: "text", autoComplete: "street-address" },
      { name: "postal_code", type: "text", autoComplete: "postal-code" },
      { name: "city", type: "text", autoComplete: "address-level2" },
      { name: "country", type: "text", autoComplete: "country-name" },
    ],
  },
  { id: "notes", fields: [{ name: "notes", type: "textarea" }] },
];

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Mirrors the backend rules (app/validation.py), which stay authoritative.
export const contactSchema = z
  .object(Object.fromEntries(CONTACT_FIELD_NAMES.map((name) => [name, z.string()])) as Record<FieldName, z.ZodString>)
  .superRefine((value, ctx) => {
    if (!value.last_name.trim() && !value.company.trim()) {
      for (const path of ["last_name", "company"]) {
        ctx.addIssue({ code: "custom", path: [path], message: strings.review.errors.identity });
      }
    }
    if (value.email.trim() && !EMAIL.test(value.email.trim())) {
      ctx.addIssue({ code: "custom", path: ["email"], message: strings.review.errors.email });
    }
  });

export function emptyContact(): Contact {
  return Object.fromEntries(CONTACT_FIELD_NAMES.map((name) => [name, ""])) as Contact;
}
