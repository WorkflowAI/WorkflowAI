import { useStripe } from '@stripe/react-stripe-js';
import { StripeElements } from '@stripe/stripe-js';
import { useCallback } from 'react';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { RequestError } from '@/lib/api/client';
import { useOrganizationSettings } from '@/store/organization_settings';
import { usePayments } from '@/store/payments';

function errorMessage(error: unknown, defaultPrefix?: string): string {
  if (error instanceof RequestError && 'statusText' in error.response) {
    if (error.response.status === 402) {
      return `Your card's security code is incorrect.`;
    }
    return String(error.response.statusText);
  }

  if (error && typeof error === 'object' && 'message' in error) {
    return error.message as string;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return defaultPrefix ? `${defaultPrefix}. Error: ${String(error)}` : `Error: ${String(error)}`;
}

export function useStripePayments() {
  const stripe = useStripe();

  const createPaymentIntent = usePayments((state) => state.createPaymentIntent);
  const addPaymentMethod = usePayments((state) => state.addPaymentMethod);

  const fetchOrganizationSettings = useOrganizationSettings((state) => state.fetchOrganizationSettings);

  const handlePaymentStatus = useCallback(
    async (clientSecret: string, amount: number) => {
      if (!stripe) return;

      const { error, paymentIntent } = await stripe.retrievePaymentIntent(clientSecret);

      if (error) throw error;

      switch (paymentIntent.status) {
        case 'succeeded':
          break;

        case 'requires_action':
        case 'requires_confirmation':
          const result = await stripe.confirmPayment({
            clientSecret,
            redirect: 'if_required',
          });

          if (result.error) {
            throw result.error;
          }

          await handlePaymentStatus(clientSecret, amount);
          break;

        case 'requires_payment_method':
          throw new Error('Payment failed. Error: Your payment method was declined.');

        default:
          throw new Error(`Payment failed. Error: [${paymentIntent.status}]`);
      }
    },
    [stripe]
  );

  const addCredits = useCallback(
    async (amountToAdd: number) => {
      if (amountToAdd <= 0) {
        return false;
      }

      try {
        const { client_secret } = await createPaymentIntent(amountToAdd);
        await handlePaymentStatus(client_secret, amountToAdd);
        await fetchOrganizationSettings();
        displaySuccessToaster(`$${amountToAdd} in Credits Added Successfully`);
        return true;
      } catch (error) {
        displayErrorToaster(errorMessage(error, 'Payment failed'));
        return false;
      }
    },
    [createPaymentIntent, fetchOrganizationSettings, handlePaymentStatus]
  );

  const createPaymentMethod = useCallback(
    async (elements: StripeElements | undefined) => {
      if (!stripe || !elements) return;

      try {
        const { paymentMethod, error } = await stripe.createPaymentMethod({
          elements,
          params: {
            type: 'card',
          },
        });

        if (error) throw error;
        if (!paymentMethod) throw new Error('No payment method created');

        await addPaymentMethod(paymentMethod.id);
        displaySuccessToaster('Payment Method Successfully Added');
      } catch (error) {
        displayErrorToaster(errorMessage(error));
        throw error;
      }
    },
    [addPaymentMethod, stripe]
  );

  return { addCredits, createPaymentMethod };
}
