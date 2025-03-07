export class CalculationUtils {
    static calculatePrice(assetPriceHex: string, scale: number): number {
        const decimalValue = parseInt(assetPriceHex, 16);
        if (isNaN(decimalValue) || scale === undefined) {
            console.warn(`Invalid AssetPrice or Scale: ${assetPriceHex}, ${scale}`);
            return 0; // Or some default value
        }
        const divisor = Math.pow(10, scale);
        return decimalValue / divisor;
    }
}