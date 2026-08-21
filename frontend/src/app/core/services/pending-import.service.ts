import { Injectable } from '@angular/core';

const DB_NAME = 'aca-pending-import';
const STORE = 'files';
const KEY = 'pending';
const MAX_BYTES = 80 * 1024 * 1024; // 80 MB

export type PendingImportRecord = {
  name: string;
  type: string;
  lastModified: number;
  blob: Blob;
};

@Injectable({ providedIn: 'root' })
export class PendingImportService {
  async save(file: File): Promise<void> {
    if (file.size > MAX_BYTES) {
      throw new Error('Arquivo muito grande para guardar temporariamente (máx. 80 MB).');
    }
    const db = await this.open();
    const record: PendingImportRecord = {
      name: file.name,
      type: file.type || 'application/octet-stream',
      lastModified: file.lastModified,
      blob: file,
    };
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('Falha ao guardar o arquivo.'));
      tx.objectStore(STORE).put(record, KEY);
    });
    db.close();
    sessionStorage.setItem('aca.pendingImportName', file.name);
  }

  async getFile(): Promise<File | null> {
    const db = await this.open();
    const record = await new Promise<PendingImportRecord | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).get(KEY);
      req.onsuccess = () => resolve(req.result as PendingImportRecord | undefined);
      req.onerror = () => reject(req.error ?? new Error('Falha ao ler o arquivo pendente.'));
    });
    db.close();
    if (!record?.blob) {
      return null;
    }
    return new File([record.blob], record.name, {
      type: record.type,
      lastModified: record.lastModified,
    });
  }

  async peekName(): Promise<string | null> {
    const fromSession = sessionStorage.getItem('aca.pendingImportName');
    if (fromSession) {
      return fromSession;
    }
    const file = await this.getFile();
    return file?.name ?? null;
  }

  async clear(): Promise<void> {
    sessionStorage.removeItem('aca.pendingImportName');
    const db = await this.open();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error('Falha ao limpar arquivo pendente.'));
      tx.objectStore(STORE).delete(KEY);
    });
    db.close();
  }

  private open(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE);
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error ?? new Error('IndexedDB indisponível.'));
    });
  }
}
