"""
邮件服务
"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from loguru import logger

from app.core.config import settings


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html: bool = False
) -> bool:
    """
    发送邮件
    
    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        html: 是否为HTML格式
    
    Returns:
        是否发送成功
    """
    # 如果没有配置邮件服务器，则跳过发送
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning(f"邮件服务未配置，跳过发送邮件到 {to_email}: {subject}")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if html:
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=True
        )
        
        logger.info(f"邮件发送成功: {to_email} - {subject}")
        return True
        
    except Exception as e:
        logger.error(f"邮件发送失败: {to_email} - {subject}, 错误: {e}")
        return False


async def send_quota_low_alert(
    to_email: str,
    username: str,
    quota: int,
    quota_used: int,
    threshold_percent: int = 20
) -> bool:
    """
    发送额度不足警告
    
    Args:
        to_email: 收件人邮箱
        username: 用户名
        quota: 总额度
        quota_used: 已使用额度
        threshold_percent: 阈值百分比
    """
    quota_remain = quota - quota_used
    percent_used = (quota_used / quota * 100) if quota > 0 else 100
    
    subject = "⚠️ 额度不足提醒 - Token Manager"
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #e74c3c;">额度不足提醒</h2>
            <p>您好，{username}，</p>
            <p>您的账户额度即将用尽，请及时充值以避免影响使用。</p>
            
            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>总额度：</strong></td>
                        <td style="text-align: right;">{quota:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>已使用：</strong></td>
                        <td style="text-align: right;">{quota_used:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>剩余：</strong></td>
                        <td style="text-align: right; color: #e74c3c; font-weight: bold;">{quota_remain:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>使用率：</strong></td>
                        <td style="text-align: right; color: #e74c3c; font-weight: bold;">{percent_used:.1f}%</td>
                    </tr>
                </table>
            </div>
            
            <p style="color: #666; font-size: 14px;">
                当额度低于 {threshold_percent}% 时，系统会自动发送此提醒。
            </p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                此邮件由 Token Manager 系统自动发送，请勿回复。
            </p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, body, html=True)


async def send_quota_change_notification(
    to_email: str,
    username: str,
    change_amount: int,
    change_type: str,
    current_quota: int,
    reason: str = ""
) -> bool:
    """
    发送额度变动通知
    
    Args:
        to_email: 收件人邮箱
        username: 用户名
        change_amount: 变动额度
        change_type: 变动类型 (increase/decrease)
        current_quota: 当前总额度
        reason: 变动原因
    """
    change_type_text = "增加" if change_type == "increase" else "减少"
    change_amount_abs = abs(change_amount)
    
    subject = f"📊 额度变动通知 - {'+' if change_type == 'increase' else '-'}{change_amount_abs:,}"
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #3498db;">额度变动通知</h2>
            <p>您好，{username}，</p>
            <p>您的账户额度发生了变动：</p>
            
            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>变动类型：</strong></td>
                        <td style="text-align: right; color: {'#27ae60' if change_type == 'increase' else '#e74c3c'};">
                            {change_type_text}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>变动额度：</strong></td>
                        <td style="text-align: right; font-weight: bold; color: {'#27ae60' if change_type == 'increase' else '#e74c3c'};">
                            {'+' if change_type == 'increase' else '-'}{change_amount_abs:,}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>当前总额度：</strong></td>
                        <td style="text-align: right;">{current_quota:,}</td>
                    </tr>
                    {f'<tr><td style="padding: 8px 0;"><strong>变动原因：</strong></td><td style="text-align: right;">{reason}</td></tr>' if reason else ''}
                </table>
            </div>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                此邮件由 Token Manager 系统自动发送，请勿回复。
            </p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, body, html=True)


async def send_daily_report(
    to_email: str,
    username: str,
    quota: int,
    quota_used: int,
    daily_used: int,
    model_usage: dict
) -> bool:
    """
    发送每日用量报表
    
    Args:
        to_email: 收件人邮箱
        username: 用户名
        quota: 总额度
        quota_used: 已使用总额度
        daily_used: 今日使用量
        model_usage: 模型使用量统计 {"model_name": count}
    """
    quota_remain = quota - quota_used
    percent_used = (quota_used / quota * 100) if quota > 0 else 100
    
    # 构建模型使用表格
    model_rows = ""
    for model, count in sorted(model_usage.items(), key=lambda x: x[1], reverse=True)[:10]:
        model_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{model}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{count:,}</td>
        </tr>
        """
    
    subject = f"📈 每日用量报表 - {daily_used:,} tokens"
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #27ae60;">每日用量报表</h2>
            <p>您好，{username}，</p>
            <p>以下是您今天的用量统计：</p>
            
            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <h3 style="margin-top: 0;">今日用量</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>今日使用：</strong></td>
                        <td style="text-align: right; font-size: 18px; color: #27ae60; font-weight: bold;">{daily_used:,} tokens</td>
                    </tr>
                </table>
            </div>
            
            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <h3 style="margin-top: 0;">额度概况</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>总额度：</strong></td>
                        <td style="text-align: right;">{quota:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>已使用：</strong></td>
                        <td style="text-align: right;">{quota_used:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>剩余：</strong></td>
                        <td style="text-align: right; color: {'#e74c3c' if percent_used > 80 else '#27ae60'}; font-weight: bold;">
                            {quota_remain:,} ({100 - percent_used:.1f}%)
                        </td>
                    </tr>
                </table>
            </div>
            
            {f'''
            <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <h3 style="margin-top: 0;">模型使用排行 (Top 10)</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">模型</th>
                        <th style="padding: 8px; text-align: right; border-bottom: 2px solid #ddd;">使用量</th>
                    </tr>
                    {model_rows}
                </table>
            </div>
            ''' if model_rows else ''}
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                此邮件由 Token Manager 系统自动发送，请勿回复。
            </p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, body, html=True)
