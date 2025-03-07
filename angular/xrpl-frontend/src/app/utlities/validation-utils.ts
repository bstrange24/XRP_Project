import * as XRPL from 'xrpl';

export class ValidationUtils {
    static isValidXrpAddress(address: string): boolean {
        return XRPL.isValidAddress(address.trim());
    }

    static isValidCommaSeparatedList(input: string): boolean {
        return input.split(',').map(el => el.trim()).every(el => el.length === 3);
    }

    static isValidNumberList(input: string): boolean {
        return input.split(',').map(el => el.trim()).every(el => !isNaN(Number(el)) && Number(el) > 0);
    }

    static isValidURI(uri: string): boolean {
        try {
            new URL(uri);
            return true;
        } catch (error) {
            return false;
        }
    }
}
