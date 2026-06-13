/**
 * Parse a backend timestamp string as UTC.
 * The backend emits naive UTC strings (no offset); we normalise them to UTC
 * so the browser renders them in the user's local timezone correctly.
 */
export const parseUTCDate = (dateStr?: string) => {
  if (!dateStr) return new Date();
  if (dateStr.endsWith("Z") || dateStr.includes("+") || (dateStr.includes("-") && dateStr.lastIndexOf("-") > 10)) {
    return new Date(dateStr);
  }
  if (dateStr.includes("T")) {
    return new Date(dateStr + "Z");
  }
  return new Date(dateStr.replace(" ", "T") + "Z");
};
