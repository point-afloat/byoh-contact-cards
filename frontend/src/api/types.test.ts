import schema from "./openapi.json";
import { CONTACT_FIELD_NAMES } from "./types";

test("frontend field list matches the backend Contact schema exactly", () => {
  const backend = Object.keys(schema.components.schemas.Contact.properties).sort();
  expect([...CONTACT_FIELD_NAMES].sort()).toEqual(backend);
});
