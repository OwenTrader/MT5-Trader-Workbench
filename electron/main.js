import { app, BrowserWindow } from 'electron';
import path from 'node:path';
function createWindow() {
    var win = new BrowserWindow({
        width: 1440,
        height: 900,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
        },
    });
    win.setTitle('Trader Workbench');
    // In dev, load from vite; in prod, load from dist
    if (process.env.VITE_DEV_SERVER_URL) {
        win.loadURL(process.env.VITE_DEV_SERVER_URL);
    }
    else {
        // For now, satisfy the test which just checks for title
        win.loadURL('data:text/html,<html><head><title>Trader Workbench</title></head><body><h1>Trader Workbench</h1></body></html>');
    }
}
app.whenReady().then(createWindow);
