export class CalculationUtils {
      // XRPL epoch offset (seconds from Unix epoch to XRPL epoch: Jan 1, 2000)
  static readonly XRPL_EPOCH_OFFSET = 946684800;
  // Allowed characters for memo_type and memo_format
  static readonly ALLOWED_CHARS = /^[A-Za-z0-9\-._~:/?#[\]@!$&'()*+,;=%]*$/;
  // Max memo size in bytes (1 KB)
  static readonly MAX_MEMO_SIZE = 1024;

    static calculatePrice(assetPriceHex: string, scale: number): number {
        const decimalValue = parseInt(assetPriceHex, 16);
        if (isNaN(decimalValue) || scale === undefined) {
            console.warn(`Invalid AssetPrice or Scale: ${assetPriceHex}, ${scale}`);
            return 0; // Or some default value
        }
        const divisor = Math.pow(10, scale);
        return decimalValue / divisor;
    }

    // Format XRPL timestamp to local date string
    static formatDate(xrplTimestamp: number): string {
      const unixTimestamp = xrplTimestamp + this.XRPL_EPOCH_OFFSET; // Adjust to Unix epoch
      const date = new Date(unixTimestamp * 1000); // Convert seconds to milliseconds
      return date.toLocaleString();
    }

    // Format time for API (e.g., "1:min")
    static formatTime(value: number, unit: string): string {
        return `${value}:${unit}`;
    }

     // Format SendMax from drops to XRP with 2 decimal places
  formatSendMax(sendMax: string): string {
    const drops = parseFloat(sendMax);
    const xrp = drops / 1000000; // Convert drops to XRP
    return isNaN(xrp) ? sendMax : xrp.toFixed(2);
  }
}