output "instance_id" {
  description = "EC2 Instance ID in Bangkok (ap-southeast-7)"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Elastic Static Public IP"
  value       = aws_eip.app_eip.public_ip
}

output "web_url" {
  description = "Live Production URL (HTTP Port 80 via Nginx)"
  value       = "http://${aws_eip.app_eip.public_ip}"
}

output "direct_streamlit_url" {
  description = "Direct Streamlit Port URL (Port 8501)"
  value       = "http://${aws_eip.app_eip.public_ip}:8501"
}

output "ssh_connection_command" {
  description = "SSH Command to connect to the server"
  value       = "ssh -i ${local_file.private_key.filename} ubuntu@${aws_eip.app_eip.public_ip}"
}
