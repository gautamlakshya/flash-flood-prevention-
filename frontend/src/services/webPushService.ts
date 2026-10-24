// Browser Web Push Subscription Service for Chungthang FFEWS PWA

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function isPushSupported(): boolean {
  return typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window;
}

export function getNotificationPermission(): NotificationPermission | 'unsupported' {
  if (!isPushSupported()) return 'unsupported';
  return Notification.permission;
}

export async function checkExistingPushSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  try {
    const registration = await navigator.serviceWorker.ready;
    return await registration.pushManager.getSubscription();
  } catch (e) {
    console.warn("Could not check existing push subscription:", e);
    return null;
  }
}

export async function subscribeToWebPush(apiUrl: string): Promise<{ success: boolean; message: string; subscription?: any }> {
  if (!isPushSupported()) {
    return {
      success: false,
      message: "Browser Web Push is not supported on this device/browser (or insecure HTTP origin)."
    };
  }

  // 1. Request user permission
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return {
      success: false,
      message: permission === 'denied'
        ? "Push notifications were blocked in browser settings. Please permit notifications to receive flood alerts."
        : "Notification permission was dismissed."
    };
  }

  // 2. Fetch VAPID Public Key from backend
  try {
    const keyRes = await fetch(`${apiUrl}/api/v1/alerts/push/vapid-public-key`);
    if (!keyRes.ok) throw new Error(`HTTP ${keyRes.status} fetching VAPID public key`);
    const keyData = await keyRes.json();
    const vapidPublicKey = keyData.publicKey;

    if (!vapidPublicKey) {
      return {
        success: false,
        message: keyData.error || "Backend has not configured a valid VAPID public key."
      };
    }

    // 3. Subscribe with Service Worker
    const registration = await navigator.serviceWorker.ready;
    const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);

    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey as unknown as BufferSource
      });
    }

    const subJson = subscription.toJSON();
    if (!subJson.endpoint || !subJson.keys) {
      throw new Error("Invalid push subscription structure returned by browser.");
    }

    // 4. Register with Backend
    const regRes = await fetch(`${apiUrl}/api/v1/alerts/push/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        endpoint: subJson.endpoint,
        keys: {
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth
        },
        user_agent: navigator.userAgent
      })
    });

    if (!regRes.ok) {
      const err = await regRes.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned ${regRes.status}`);
    }

    return {
      success: true,
      message: "Browser successfully registered to receive real-time push flood alerts!",
      subscription: subJson
    };

  } catch (e: any) {
    return {
      success: false,
      message: `Failed to register push subscription: ${e.message || String(e)}`
    };
  }
}

export async function unsubscribeFromWebPush(apiUrl: string): Promise<{ success: boolean; message: string }> {
  if (!isPushSupported()) {
    return { success: false, message: "Push not supported." };
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      const endpoint = subscription.endpoint;
      await subscription.unsubscribe();

      await fetch(`${apiUrl}/api/v1/alerts/push/unsubscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint })
      }).catch(() => null);
    }

    return {
      success: true,
      message: "Browser successfully unsubscribed from push notifications."
    };
  } catch (e: any) {
    return {
      success: false,
      message: `Failed to unsubscribe: ${e.message}`
    };
  }
}
