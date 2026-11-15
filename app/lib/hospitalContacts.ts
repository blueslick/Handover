// Who to contact at each hospital (T80). A contact belongs to the hospital, not to one
// patient's record, so it lives in this small list and is looked up by the hospital's
// letter. The records themselves are not changed, and no contact is read from them.
// Hospitals A, B and C are made up, so these contacts are made up too: the phone numbers
// are in a range kept for examples and the email addresses end in ".example", which can
// never be a real address. The app always labels them "example contact".
export interface HospitalContact {
  office: string;
  phone: string;
  email: string;
}

export const HOSPITAL_CONTACTS: Record<string, HospitalContact> = {
  A: { office: "Medical records office", phone: "555-0101", email: "records@hospital-a.example" },
  B: { office: "Medical records office", phone: "555-0102", email: "records@hospital-b.example" },
  C: { office: "Pharmacy and records desk", phone: "555-0103", email: "records@hospital-c.example" },
};

export function hospitalContact(letter: string): HospitalContact | null {
  return HOSPITAL_CONTACTS[letter] ?? null;
}
