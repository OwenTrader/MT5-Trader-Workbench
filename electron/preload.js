import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('electron', {
    ipcRenderer: {
        send: function (channel, data) { return ipcRenderer.send(channel, data); },
        on: function (channel, func) {
            ipcRenderer.on(channel, function (event) {
                var args = [];
                for (var _i = 1; _i < arguments.length; _i++) {
                    args[_i - 1] = arguments[_i];
                }
                return func.apply(void 0, args);
            });
        },
    },
});
