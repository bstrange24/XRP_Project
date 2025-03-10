import * as XRPL from 'xrpl';

export class ValidationUtils {
     static isValidXrpAddress(address: string): boolean {
          if (!address || typeof address !== 'string') return false;
          return XRPL.isValidAddress(address.trim());
     }

     static isValidXrpSeed(seed: string): boolean {
          try {
            return seed.startsWith('sEd') && seed.length >= 29 && seed.length <= 35;
          } catch (error) {
            console.error('Error validating XRP seed:', error);
            return false;
          }
        }

     static async isValidLedgerIndex(ledgerIndex: number): Promise<boolean> {
          try {
               const client = new XRPL.Client('wss://s.altnet.rippletest.net:51233');
               await client.connect();
               const response = await client.request({
                    command: 'ledger',
                    ledger_index: ledgerIndex,
                    transactions: false,
                    expand: false,
               });
               await client.disconnect();
               return response.result.validated === true;
          } catch (error) {
               console.error('Error validating ledger index:', error);
               return false;
          }
     }

     static isValidCurrencyCode(code: string): boolean {
          if (!code || typeof code !== 'string') return false;
          const trimmedCode = code.trim().toUpperCase();
          return /^[A-Z]{3}$/.test(trimmedCode); // Matches exactly 3 uppercase letters
     }

     // Validate limit (positive number)
     static isValidLimit(limit: number): boolean {
          const num = Number(limit);
          return !isNaN(num) && num > 0;
     }

     static isValidCommaSeparatedList(input: string): boolean {
          return input.split(',').map(el => el.trim()).every(el => el.length === 3);
     }

     static isValidNumberList(input: string): boolean {
          return input.split(',').map(el => el.trim()).every(el => !isNaN(Number(el)) && Number(el) > 0);
     }

     // Validate amount (positive number as string)
     static isValidAmount(amount: any): boolean {
          let amountStr: string;
          if (typeof amount === 'number') {
               amountStr = amount.toString(); // Convert number to string
               console.log('Converted amount to string:', amountStr);
          } else if (typeof amount === 'string') {
               amountStr = amount;
          } else {
               return false;
          }
          const trimmedAmount = amountStr.trim();
          const num = Number(trimmedAmount);
          return !isNaN(num) && num > 0;
     }

     static isValidURI(uri: string): boolean {
          try {
               new URL(uri);
               return true;
          } catch (error) {
               return false;
          }
     }

     static areFieldsValid(accountSeed: string, document: string, uri: string, didData: string): boolean {
          return (
               !!accountSeed.trim() &&
               !!document.trim() &&
               !!uri.trim() &&
               !!didData.trim()
          );
     }

     static isSyntacticallyValidLedgerIndex(index: string | number): boolean {
          const num = Number(index);
          return Number.isInteger(num) && num > 0 && num <= 4294967295;
     }
}
