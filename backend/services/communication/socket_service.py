import asyncio
import logging
import socketio
from typing import Dict, Any, Callable, Optional, List
from backend.services.reporting.progress_tracker import ProgressTracker
from backend.services.reporting.error_reporter import ErrorReporter

class SocketService:
    """Manages Socket.IO connections and message handling."""
    
    def __init__(self, sio: socketio.AsyncServer, logger: logging.Logger, 
                 progress_tracker: Optional[ProgressTracker] = None, 
                 error_reporter: Optional[ErrorReporter] = None):
        self.sio = sio
        self.logger = logger
        self.progress_tracker = progress_tracker
        self.error_reporter = error_reporter
        self.active_sessions = {}
        self.handlers = {}
        self.progress_sub_id = None
        self.error_sub_id = None
        
        # Register default event handlers
        self._register_default_handlers()
        
        # Subscribe to progress and error events if available
        if progress_tracker:
            self.progress_sub_id = progress_tracker.subscribe(self._on_progress_update)
        if error_reporter:
            self.error_sub_id = error_reporter.subscribe(self._on_error_event)
    
    def _register_default_handlers(self):
        """Register the default Socket.IO event handlers."""
        self.register_handler('connect', self._handle_connect)
        self.register_handler('disconnect', self._handle_disconnect)
        
        # Register all handlers to the socketio server
        for event, handler in self.handlers.items():
            self.sio.on(event, handler)
    
    def register_handler(self, event: str, handler: Callable):
        """Register a custom event handler."""
        self.handlers[event] = handler
        self.sio.on(event, handler)
    
    async def _handle_connect(self, sid, environ):
        """Handle client connection."""
        self.logger.debug(f"Client connected: {sid}")
        self.active_sessions[sid] = {
            'connected_at': asyncio.get_event_loop().time(),
            'last_activity': asyncio.get_event_loop().time(),
            'client_info': environ.get('HTTP_USER_AGENT', 'Unknown'),
            'project': None
        }
    
    async def _handle_disconnect(self, sid):
        """Handle client disconnection."""
        if sid in self.active_sessions:
            project = self.active_sessions[sid].get('project')
            duration = asyncio.get_event_loop().time() - self.active_sessions[sid]['connected_at']
            self.logger.debug(f"Client disconnected: {sid}, was connected for {duration:.2f}s, project: {project}")
            del self.active_sessions[sid]
    
    async def emit(self, event: str, data: Dict[str, Any], room: Optional[str] = None):
        """Emit an event to one or all clients."""
        try:
            if room:
                await self.sio.emit(event, data, to=room)
            else:
                await self.sio.emit(event, data)
        except Exception as e:
            self.logger.error(f"Error emitting {event}: {str(e)}")
    
    def emit_async(self, event: str, data: Dict[str, Any], room: Optional[str] = None):
        """Create a task to emit an event asynchronously."""
        asyncio.create_task(self.emit(event, data, room))
    
    async def emit_error(self, sid: str, message: str):
        """Emit an error to a specific client."""
        await self.emit('error', {'message': message}, room=sid)
    
    async def _on_progress_update(self, progress_data: Dict[str, Any]):
        """Handle progress updates from ProgressTracker."""
        # Find all sessions interested in this job_id
        job_id = progress_data.get('job_id')
        interested_sessions = [
            sid for sid, session in self.active_sessions.items()
            if session.get('project') == job_id
        ]
        
        # Emit progress to interested sessions
        for sid in interested_sessions:
            await self.emit('progress', progress_data, room=sid)
    
    async def _on_error_event(self, error_data: Dict[str, Any]):
        """Handle error events from ErrorReporter."""
        # For critical errors, notify all connected clients
        if error_data.get('severity') == 'critical':
            await self.emit('system_alert', {
                'message': 'A system error has occurred. Some features may be unavailable.',
                'severity': 'critical'
            })
        
        # For component-specific errors, notify affected sessions
        context = error_data.get('context', {})
        
        if 'session_id' in context and context['session_id'] in self.active_sessions:
            # This error is specific to a session
            await self.emit_error(
                context['session_id'], 
                error_data.get('user_message', 'An error occurred')
            )
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get information about active sessions."""
        current_time = asyncio.get_event_loop().time()
        active_sessions = []
        
        for sid, session in self.active_sessions.items():
            session_info = {
                'session_id': sid,
                'duration': current_time - session['connected_at'],
                'last_activity': current_time - session['last_activity'],
                'client_info': session['client_info'],
                'project': session['project']
            }
            active_sessions.append(session_info)
            
        return active_sessions
            
    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self.active_sessions) 