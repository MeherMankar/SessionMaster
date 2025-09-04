import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import db
from utils import sanitize_log_input
import logging

class Analytics:
    def __init__(self):
        pass
    
    def get_user_dashboard(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive dashboard data for user"""
        try:
            # Get user sessions
            sessions = db.get_user_sessions(user_id)
            
            # Get recent analytics
            recent_actions = db.get_user_analytics(user_id, limit=50)
            
            # Calculate statistics
            stats = self._calculate_user_stats(user_id, recent_actions)
            
            # Get message templates count
            templates = db.get_message_templates(user_id)
            
            dashboard = {
                "user_id": user_id,
                "sessions_count": len(sessions),
                "active_sessions": len([s for s in sessions if s['is_active']]),
                "templates_count": len(templates),
                "total_actions": len(recent_actions),
                "stats": stats,
                "recent_sessions": sessions[:5],  # Last 5 sessions
                "recent_actions": recent_actions[:10]  # Last 10 actions
            }
            
            return dashboard
            
        except Exception as e:
            logging.error(f"Error generating dashboard: {sanitize_log_input(str(e))}")
            return {"error": str(e)}
    
    def _calculate_user_stats(self, user_id: int, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate user statistics from actions"""
        stats = {
            "messages_sent": 0,
            "channels_joined": 0,
            "contacts_exported": 0,
            "sessions_created": 0,
            "most_active_day": None,
            "activity_by_day": {},
            "action_types": {}
        }
        
        for action in actions:
            action_type = action.get('action', '')
            
            # Count action types
            stats["action_types"][action_type] = stats["action_types"].get(action_type, 0) + 1
            
            # Count specific actions
            if 'message_sent' in action_type:
                stats["messages_sent"] += 1
            elif 'channel_join' in action_type:
                stats["channels_joined"] += 1
            elif 'contacts_export' in action_type:
                stats["contacts_exported"] += 1
            elif 'session_create' in action_type:
                stats["sessions_created"] += 1
            
            # Activity by day
            if action.get('timestamp'):
                try:
                    date = datetime.fromisoformat(action['timestamp']).date()
                    day_str = date.strftime('%Y-%m-%d')
                    stats["activity_by_day"][day_str] = stats["activity_by_day"].get(day_str, 0) + 1
                except:
                    pass
        
        # Find most active day
        if stats["activity_by_day"]:
            stats["most_active_day"] = max(stats["activity_by_day"], key=stats["activity_by_day"].get)
        
        return stats
    
    def get_session_analytics(self, user_id: int, session_name: str) -> Dict[str, Any]:
        """Get analytics for a specific session"""
        try:
            session = db.get_session_by_name(user_id, session_name)
            if not session:
                return {"error": "Session not found"}
            
            # Get session-specific actions
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM analytics 
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (user_id, session['id']))
                actions = [dict(row) for row in cursor.fetchall()]
            
            analytics = {
                "session_name": session_name,
                "session_id": session['id'],
                "created_at": session['created_at'],
                "last_used": session['last_used'],
                "total_actions": len(actions),
                "actions": actions[:20],  # Last 20 actions
                "action_summary": self._summarize_actions(actions)
            }
            
            return analytics
            
        except Exception as e:
            logging.error(f"Error getting session analytics: {sanitize_log_input(str(e))}")
            return {"error": str(e)}
    
    def _summarize_actions(self, actions: List[Dict[str, Any]]) -> Dict[str, int]:
        """Summarize actions by type"""
        summary = {}
        for action in actions:
            action_type = action.get('action', 'unknown')
            summary[action_type] = summary.get(action_type, 0) + 1
        return summary
    
    def get_usage_report(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Generate usage report for specified period"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM analytics 
                    WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp DESC
                """, (user_id, start_date.isoformat(), end_date.isoformat()))
                actions = [dict(row) for row in cursor.fetchall()]
            
            # Generate daily activity
            daily_activity = {}
            current_date = start_date.date()
            while current_date <= end_date.date():
                daily_activity[current_date.strftime('%Y-%m-%d')] = 0
                current_date += timedelta(days=1)
            
            for action in actions:
                try:
                    action_date = datetime.fromisoformat(action['timestamp']).date()
                    date_str = action_date.strftime('%Y-%m-%d')
                    if date_str in daily_activity:
                        daily_activity[date_str] += 1
                except:
                    pass
            
            report = {
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_actions": len(actions),
                "daily_activity": daily_activity,
                "action_breakdown": self._summarize_actions(actions),
                "peak_activity_day": max(daily_activity, key=daily_activity.get) if daily_activity else None,
                "average_daily_actions": len(actions) / days if days > 0 else 0
            }
            
            return report
            
        except Exception as e:
            logging.error(f"Error generating usage report: {sanitize_log_input(str(e))}")
            return {"error": str(e)}
    
    def export_analytics(self, user_id: int, format_type: str = "json") -> str:
        """Export user analytics in specified format"""
        try:
            dashboard = self.get_user_dashboard(user_id)
            usage_report = self.get_usage_report(user_id, 90)  # 90 days
            
            export_data = {
                "export_date": datetime.now().isoformat(),
                "user_id": user_id,
                "dashboard": dashboard,
                "usage_report": usage_report
            }
            
            if format_type == "json":
                return json.dumps(export_data, indent=2, ensure_ascii=False)
            else:
                # Could add CSV or other formats here
                return json.dumps(export_data, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logging.error(f"Error exporting analytics: {sanitize_log_input(str(e))}")
            return json.dumps({"error": str(e)})

# Global analytics instance
analytics = Analytics()