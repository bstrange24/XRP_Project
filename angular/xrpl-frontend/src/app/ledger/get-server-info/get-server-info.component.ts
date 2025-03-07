import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

// Define the interface for the API response
export interface ServerInfoResponse {
     status: string;
     message: string;
     result: {
          info: {
               build_version: string;
               complete_ledgers: string;
               hostid: string;
               initial_sync_duration_us: string;
               io_latency_ms: number;
               jq_trans_overflow: string;
               last_close: {
                    converge_time_s: number;
                    proposers: number;
               };
               load_factor: number;
               network_id: number;
               peer_disconnects: string;
               peer_disconnects_resources: string;
               peers: number;
               ports: { port: string; protocol: string[] }[];
               pubkey_node: string;
               server_state: string;
               server_state_duration_us: string;
               state_accounting: {
                    connected: { duration_us: string; transitions: string };
                    disconnected: { duration_us: string; transitions: string };
                    full: { duration_us: string; transitions: string };
                    syncing: { duration_us: string; transitions: string };
                    tracking: { duration_us: string; transitions: string };
               };
               time: string;
               uptime: number;
               validated_ledger: {
                    age: number;
                    base_fee_xrp: number;
                    hash: string;
                    reserve_base_xrp: number;
                    reserve_inc_xrp: number;
                    seq: number;
               };
               validation_quorum: number;
          };
     };
}

@Component({
     selector: 'app-get-server-info',
     standalone: true,
     imports: [
          CommonModule,
          FormsModule,
          MatCardModule,
          MatFormFieldModule,
          MatInputModule,
          MatButtonModule
     ],
     templateUrl: './get-server-info.component.html',
     styleUrls: ['./get-server-info.component.css']
})
export class GetServerInfoComponent implements OnInit {
     serverInfo: ServerInfoResponse | null = null;
     isLoading: boolean = false;
     errorMessage: string = '';

     constructor(
          private readonly snackBar: MatSnackBar,
          private readonly http: HttpClient
     ) { }

     ngOnInit(): void {
          this.getServerInfo(); // Fetch server info automatically on load
     }

     async getServerInfo(): Promise<void> {
          this.isLoading = true;
          this.errorMessage = '';
          this.serverInfo = null;

          try {
               const response = await firstValueFrom(this.http.get<ServerInfoResponse>('http://127.0.0.1:8000/xrpl/ledger/server-info/'));
               this.serverInfo = response;
               this.isLoading = false;
               console.log('Server info retrieved:', response);
          } catch (error: any) {
               console.error('Error retrieving server info:', error);
               let errorMessage: string;
               if (error instanceof Error) {
                    errorMessage = error.message;
               } else if (typeof error === 'object' && error !== null && 'message' in error) {
                    errorMessage = (error).message;
               } else {
                    errorMessage = 'An unexpected error occurred while retrieving server info.';
               }
               this.errorMessage = errorMessage;
               this.snackBar.open(this.errorMessage, 'Close', {
                    duration: 3000,
                    panelClass: ['error-snackbar']
               });
               this.isLoading = false;
          }
     }
}