import axe from "axe-core";

/**
 * Fails with a readable list when the rendered markup breaks an accessibility rule.
 * Colour contrast needs real layout and colours, which jsdom does not have; it is checked
 * separately in the browser (Lighthouse, task 5.6 of the importer change).
 */
export async function expectNoAccessibilityViolations(root: Element | Document = document.body) {
  const results = await axe.run(root as Element, { rules: { "color-contrast": { enabled: false } } });
  const found = results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} element(s))`);
  expect(found).toEqual([]);
}
