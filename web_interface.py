from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import asyncio
import json
import io
from datetime import datetime
from database import db
from analytics import analytics
from session_operations import *
from session_manager import get_session_info
from utils import sanitize_log_input
import logging

app = Flask(__name__)
CORS(app)

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/api/users/<int:user_id>/dashboard')
def get_user_dashboard(user_id):
    """Get user dashboard data"""
    try:
        dashboard_data = analytics.get_user_dashboard(user_id)
        return jsonify(dashboard_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/sessions')
def get_user_sessions(user_id):
    """Get user sessions"""
    try:
        sessions = db.get_user_sessions(user_id)
        return jsonify(sessions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/sessions/<session_name>/info')
def get_session_info_api(user_id, session_name):
    """Get session information"""
    try:
        session = db.get_session_by_name(user_id, session_name)
        if not session:
            return jsonify({"error": "Session not found"}), 404
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    info = loop.run_until_complete(get_session_info(session['session_path']))
    loop.close()

    return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/sessions/<session_name>/analytics')
def get_session_analytics_api(user_id, session_name):
    """Get session analytics"""
    try:
        analytics_data = analytics.get_session_analytics(user_id, session_name)
        return jsonify(analytics_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/send-message', methods=['POST'])
def send_message_api(user_id):
    """Send message via API"""
    try:
        data = request.json
        session_name = data.get('session_name')
        recipient = data.get('recipient')
        message = data.get('message')
        
        session = db.get_session_by_name(user_id, session_name)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            send_message_to_user(session['session_path'], recipient, message)
        )
        loop.close()
        
        # Log action
        db.log_action(user_id, 'message_sent_api', {
            'recipient': recipient,
            'success': success
        }, session['id'])
        
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/bulk-send', methods=['POST'])
def bulk_send_api(user_id):
    """Bulk send messages via API"""
    try:
        data = request.json
        session_name = data.get('session_name')
        recipients = data.get('recipients', [])
        message = data.get('message')
        delay = data.get('delay', 5)
        
        session = db.get_session_by_name(user_id, session_name)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            bulk_send_messages(session['session_path'], recipients, message, delay)
        )
        loop.close()
        
        # Log action
        db.log_action(user_id, 'bulk_message_sent', {
            'recipients_count': len(recipients),
            'success_count': sum(1 for r in results.values() if r)
        }, session['id'])
        
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/subscribe-channels', methods=['POST'])
def bulk_subscribe_api(user_id):
    """Bulk subscribe to channels via API"""
    try:
        data = request.json
        session_name = data.get('session_name')
        channels = data.get('channels', [])
        delay = data.get('delay', 5)
        
        session = db.get_session_by_name(user_id, session_name)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            bulk_subscribe(session['session_path'], channels, delay)
        )
        loop.close()
        
        # Log action
        db.log_action(user_id, 'bulk_channel_subscribe', {
            'channels_count': len(channels),
            'success_count': sum(1 for r in results.values() if r)
        }, session['id'])
        
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/export-contacts/<session_name>')
def export_contacts_api(user_id, session_name):
    """Export contacts via API"""
    try:
        format_type = request.args.get('format', 'txt')
        
        session = db.get_session_by_name(user_id, session_name)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        contacts_file = loop.run_until_complete(
            export_contacts(session['session_path'], format_type)
        )
        loop.close()
        
        # Log action
        db.log_action(user_id, 'contacts_exported', {
            'format': format_type
        }, session['id'])
        
        return send_file(
            contacts_file,
            as_attachment=True,
            download_name=contacts_file.name,
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/templates')
def get_templates_api(user_id):
    """Get message templates"""
    try:
        templates = db.get_message_templates(user_id)
        return jsonify(templates)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/templates', methods=['POST'])
def save_template_api(user_id):
    """Save message template"""
    try:
        data = request.json
        name = data.get('name')
        content = data.get('content')
        
        db.save_message_template(user_id, name, content)
        db.log_action(user_id, 'template_saved', {'name': name})
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/schedule-message', methods=['POST'])
def schedule_message_api(user_id):
    """Schedule a message"""
    try:
        data = request.json
        session_name = data.get('session_name')
        recipient = data.get('recipient')
        message = data.get('message')
        scheduled_time = datetime.fromisoformat(data.get('scheduled_time'))
        
        session = db.get_session_by_name(user_id, session_name)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        message_id = db.schedule_message(
            user_id, session['id'], recipient, message, scheduled_time
        )
        
        db.log_action(user_id, 'message_scheduled', {
            'recipient': recipient,
            'scheduled_time': scheduled_time.isoformat()
        }, session['id'])
        
        return jsonify({"message_id": message_id, "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/usage-report')
def get_usage_report_api(user_id):
    """Get usage report"""
    try:
        days = int(request.args.get('days', 30))
        report = analytics.get_usage_report(user_id, days)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/<int:user_id>/export-analytics')
def export_analytics_api(user_id):
    """Export analytics data"""
    try:
        format_type = request.args.get('format', 'json')
        data = analytics.export_analytics(user_id, format_type)
        
        filename = f"analytics_{user_id}_{datetime.now().strftime('%Y%m%d')}.{format_type}"
        
        return send_file(
            io.BytesIO(data.encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)