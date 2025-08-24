const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Keep a global reference of the window object
let mainWindow;
let flaskProcess;

// Flask server configuration
const FLASK_PORT = 5001;
const FLASK_HOST = 'localhost';

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true
    },
    icon: path.join(__dirname, 'assets', 'icon.png'), // We'll create this
    titleBarStyle: 'default',
    show: false // Don't show until ready
  });

  // Set application menu
  const { Menu } = require('electron');
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'New Document',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.reload();
          }
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About Financial Document Processor',
          click: () => {
            shell.openExternal('https://github.com/ankithn30/FinTech-Hackathon');
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);

  // Wait for Flask server to start, then load the page
  waitForFlaskServer(() => {
    mainWindow.loadURL(`http://${FLASK_HOST}:${FLASK_PORT}`);
    
    // Show window when ready to prevent visual flash
    mainWindow.once('ready-to-show', () => {
      mainWindow.show();
      
      // Focus on window
      if (process.platform === 'darwin') {
        app.dock.show();
      }
    });
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Emitted when the window is closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle window events
  mainWindow.on('page-title-updated', (event) => {
    event.preventDefault();
  });

  // Set custom title
  mainWindow.setTitle('Financial Document Processing System');
}

function startFlaskServer() {
  console.log('Starting Flask server...');
  
  // Determine Python executable
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  
  // Start Flask server
  flaskProcess = spawn(pythonCmd, ['app.py'], {
    cwd: __dirname,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  flaskProcess.stdout.on('data', (data) => {
    console.log(`Flask stdout: ${data}`);
  });

  flaskProcess.stderr.on('data', (data) => {
    console.log(`Flask stderr: ${data}`);
  });

  flaskProcess.on('close', (code) => {
    console.log(`Flask process exited with code ${code}`);
  });

  flaskProcess.on('error', (error) => {
    console.error('Failed to start Flask server:', error);
  });
}

function waitForFlaskServer(callback) {
  const http = require('http');
  
  const checkServer = () => {
    const req = http.request({
      hostname: FLASK_HOST,
      port: FLASK_PORT,
      path: '/',
      method: 'GET',
      timeout: 1000
    }, (res) => {
      console.log('Flask server is ready!');
      callback();
    });

    req.on('error', () => {
      console.log('Waiting for Flask server...');
      setTimeout(checkServer, 1000);
    });

    req.on('timeout', () => {
      req.destroy();
      setTimeout(checkServer, 1000);
    });

    req.end();
  };

  checkServer();
}

function stopFlaskServer() {
  if (flaskProcess) {
    console.log('Stopping Flask server...');
    flaskProcess.kill('SIGTERM');
    
    // Force kill if it doesn't stop gracefully
    setTimeout(() => {
      if (flaskProcess && !flaskProcess.killed) {
        flaskProcess.kill('SIGKILL');
      }
    }, 5000);
  }
}

// App event handlers
app.whenReady().then(() => {
  // Start Flask server first
  startFlaskServer();
  
  // Create window
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopFlaskServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopFlaskServer();
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    shell.openExternal(navigationUrl);
  });
});

// Handle certificate errors
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
  if (url.startsWith(`http://${FLASK_HOST}:${FLASK_PORT}`)) {
    // Allow local Flask server
    event.preventDefault();
    callback(true);
  } else {
    callback(false);
  }
});
