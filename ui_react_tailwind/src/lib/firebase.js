/**
 * Firebase initialisation.
 *
 * These values are the Firebase *web* config. They are public by design — they
 * ship in every client bundle and are not credentials. What actually protects
 * the data is Firestore security rules plus Firebase Auth. Never put a service
 * account key here.
 *
 * Values come from Vite env vars (VITE_FIREBASE_*) so the project can be changed
 * without editing code; the defaults target the existing project.
 */

import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const env = import.meta.env ?? {};

// Auth + Firestore only need apiKey / authDomain / projectId. appId and
// messagingSenderId are for Analytics and friends, so they are deliberately
// omitted — that removes the "register a web app" setup step entirely.
const firebaseConfig = {
  apiKey: env.VITE_FIREBASE_API_KEY ?? 'AIzaSyDI1reM4nK4fxCYiNTadonchAiroc-86MI',
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN ?? 'table-93579.firebaseapp.com',
  projectId: env.VITE_FIREBASE_PROJECT_ID ?? 'table-93579',
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth = getAuth(firebaseApp);
export const db = getFirestore(firebaseApp);

export const googleProvider = new GoogleAuthProvider();
// Always let the user pick which Google account to use.
googleProvider.setCustomParameters({ prompt: 'select_account' });

export const isFirebaseConfigured = () => Boolean(firebaseConfig.apiKey);
