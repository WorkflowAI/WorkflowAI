import { produce } from 'immer';
import { useEffect } from 'react';
import { create } from 'zustand';
import { client } from '@/lib/api';
import {
  AutomaticPaymentRequest,
  CreatePaymentIntentRequest,
  CustomerCreatedResponse,
  PaymentIntentCreatedResponse,
  PaymentMethodResponse,
} from '@/types/workflowAI';
import { useOrganizationSettings } from './organization_settings';

interface PaymentsState {
  isLoading: boolean;

  isPaymentMethodInitialized: boolean;

  paymentMethod: PaymentMethodResponse | undefined;

  addPaymentMethod: (paymentMethodId: string) => Promise<void>;
  getPaymentMethod: () => Promise<void>;
  createPaymentIntent: (amount: number) => Promise<PaymentIntentCreatedResponse>;
  updateAutomaticPayment: (optIn: boolean, threshold: number | null, balanceToMaintain: number | null) => Promise<void>;
  deletePaymentMethod: () => Promise<void>;
}

export const usePayments = create<PaymentsState>((set) => ({
  isLoading: false,

  isPaymentMethodInitialized: false,

  paymentMethodId: undefined,
  paymentMethod: undefined,

  getPaymentMethod: async () => {
    try {
      const response = await client.get<PaymentMethodResponse | null>(
        `/api/data/organization/payments/payment-methods`
      );
      set(
        produce((state: PaymentsState) => {
          state.paymentMethod = !!response ? response : undefined;
        })
      );
    } catch (error) {
      console.error(error);
    } finally {
      set(
        produce((state: PaymentsState) => {
          state.isPaymentMethodInitialized = true;
        })
      );
    }
  },

  addPaymentMethod: async (paymentMethodId: string) => {
    set(
      produce((state: PaymentsState) => {
        state.isLoading = true;
      })
    );
    try {
      await client.post<{ payment_method_id: string }, PaymentMethodResponse>(
        `/api/data/organization/payments/payment-methods`,
        {
          payment_method_id: paymentMethodId,
        }
      );
    } catch (error) {
      throw error;
    } finally {
      set(
        produce((state: PaymentsState) => {
          state.isLoading = false;
        })
      );
    }

    await usePayments.getState().getPaymentMethod();
  },

  createPaymentIntent: async (amount: number) => {
    const response = await client.post<CreatePaymentIntentRequest, PaymentIntentCreatedResponse>(
      `/api/data/organization/payments/payment-intents`,
      {
        amount,
      }
    );

    return response;
  },

  updateAutomaticPayment: async (optIn: boolean, threshold: number | null, balanceToMaintain: number | null) => {
    try {
      await client.put<AutomaticPaymentRequest>(`/api/data/organization/payments/automatic-payments`, {
        opt_in: optIn,
        threshold,
        balance_to_maintain: balanceToMaintain,
      });
      await useOrganizationSettings.getState().fetchOrganizationSettings();
    } catch (error) {
      console.error(error);
    }
  },

  deletePaymentMethod: async () => {
    try {
      await client.del<void>(`/api/data/organization/payments/payment-methods`);
      await useOrganizationSettings.getState().fetchOrganizationSettings();
      await usePayments.getState().getPaymentMethod();
    } catch (error) {
      console.error(error);
    }
  },

  retryAutomaticPayment: async () => {
    await client.post(`/api/data/organization/payments/automatic-payments/retry`, undefined);
    await useOrganizationSettings.getState().fetchOrganizationSettings();
  },
}));

export const useOrFetchPayments = () => {
  const paymentMethod = usePayments((state) => state.paymentMethod);
  const isLoading = usePayments((state) => state.isLoading);
  const isInitialized = usePayments((state) => state.isPaymentMethodInitialized);
  const getPaymentMethod = usePayments((state) => state.getPaymentMethod);

  useEffect(() => {
    if (!isInitialized) {
      getPaymentMethod();
    }
  }, [getPaymentMethod, isInitialized]);

  return {
    paymentMethod,
    isLoading,
    isInitialized,
  };
};
