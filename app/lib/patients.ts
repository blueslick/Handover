// The patient's name, date of birth and sex for the banner (T81). They are not in the merged
// record, so they come from app/data/patients.json, which scripts/make-patients.mjs builds
// from each patient's own Hospital A record. A patient with no entry (a live run on the
// laptop, for example) simply shows the ID.
import patientsFile from "../data/patients.json";

export interface PatientDetails {
  family: string;
  given: string;
  dob: string;
  sex: string;
}

const PATIENTS = patientsFile.patients as Record<string, PatientDetails>;

export function patientDetails(id: string): PatientDetails | null {
  return PATIENTS[id] ?? null;
}

// Age in whole years on a given day (today by default), worked out from the date of birth.
export function ageOn(dob: string, day: Date = new Date()): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dob);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  let age = day.getFullYear() - y;
  // Not yet had this year's birthday: one year younger.
  if (day.getMonth() + 1 < mo || (day.getMonth() + 1 === mo && day.getDate() < d)) age -= 1;
  return age >= 0 ? age : null;
}
