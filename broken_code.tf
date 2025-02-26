resource "aws_instance" "example" {
  ami = "ami-123456"
  instance_type = "t2.micro"
  security_group = aws_security_group.example.id
}

resource "aws_security_group" "example" {
  name = "example_sg"
  description = "Example security group"
}