import { MatSnackBar } from '@angular/material/snack-bar';

export function handleError(
    error: any,
    snackBar: MatSnackBar,
    action: string = 'performing an action',
    options: {
        setErrorMessage?: (msg: string) => void;
        setLoading?: (loading: boolean) => void;
        setFetched?: (fetched: boolean) => void;
    } = {}
): string {
    console.error(`Error ${action}:`, error);
    let errorMessage: string;
    if (error instanceof Error) {
        errorMessage = error.message;
    } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = error.error.message; // Type assertion to access message
    } else {
        errorMessage = `An unexpected error occurred while ${action}.`;
    }

    // Display snackbar notification
    snackBar.open(errorMessage, 'Close', {
        duration: 3000,
        panelClass: ['error-snackbar'],
    });

    // Apply optional setters
    if (options.setErrorMessage) {
        options.setErrorMessage(errorMessage);
    }
    if (options.setLoading) {
        options.setLoading(false);
    }
    if (options.setFetched) {
        options.setFetched(true);
    }

    return errorMessage; // Return for potential further use
}