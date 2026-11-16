/**
 * Published demo logins, shown on the sign-in page so anyone can try the app.
 * They mirror DEMO_USERS in app/seed_demo.py (keep the two in sync). The admin account is
 * deliberately absent: on the public deployment it has a private password.
 */
export const DEMO_ACCOUNTS = [
  { role: "Supervisor", username: "maria", password: "SupPass123" },
  { role: "Technician", username: "ravi", password: "TechPass123" },
] as const;
