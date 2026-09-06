/** Drafts show up locally so they can be previewed; production builds exclude them. */
export const INCLUDE_DRAFTS = process.env.NODE_ENV !== "production";
