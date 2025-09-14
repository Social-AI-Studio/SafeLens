import 'next-auth';
import type { DefaultSession } from 'next-auth';
import 'next-auth/jwt';

// Define the shape of the registration data we store
interface RegistrationData {
  id: string;
  session_uuid: string;
  /** Optional user display name */
  name?: string;
  /** Optional user email */
  email?: string;
  image?: string;
}

/**
 * Module augmentation for `next-auth` types.
 * Allows us to add custom properties to the `Session` object
 * and the `JWT` token.
 *
 * @see https://next-auth.js.org/getting-started/typescript
 */

declare module 'next-auth' {
  /**
   * Extends the built-in `Session` type to add our custom properties.
   */
  interface Session {
    user: {
      /** The user's id from the OIDC provider. */
      id: string;
    } & DefaultSession['user']; // Keep the default properties
    
    /** Flag to indicate if the user needs to complete registration steps. */
    needsRegistration?: boolean;
    /** Registration data for backend registration. */
    registrationData?: RegistrationData;
  }
}

declare module 'next-auth/jwt' {
  /**
   * Extends the built-in `JWT` type to add our custom properties.
   */
  interface JWT {
    /** Flag to indicate if the user needs to complete registration steps. */
    needsRegistration?: boolean;
    /** Data collected during sign-in to be used for registration. */
    registrationData?: RegistrationData;
  }
}
