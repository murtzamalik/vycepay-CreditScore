###############################################################################
# VyceScore — Networking Module
# VPC, public/private subnets, NAT gateway, internet gateway
###############################################################################

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-vycescore-vpc"
    Environment = var.environment
    Project     = "vycescore"
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Internet Gateway
# ---------------------------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.environment}-vycescore-igw"
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Public Subnets
# ---------------------------------------------------------------------------
resource "aws_subnet" "public" {
  count                   = var.az_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                                           = "${var.environment}-public-${local.azs[count.index]}"
    Environment                                    = var.environment
    "kubernetes.io/role/elb"                        = "1"
    "kubernetes.io/cluster/${var.environment}-vycescore" = "shared"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "${var.environment}-public-rt"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "public" {
  count          = var.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# NAT Gateway (one per AZ for HA in production, single for dev/staging)
# ---------------------------------------------------------------------------
resource "aws_eip" "nat" {
  count  = var.single_nat_gateway ? 1 : var.az_count
  domain = "vpc"

  tags = {
    Name        = "${var.environment}-nat-eip-${count.index}"
    Environment = var.environment
  }
}

resource "aws_nat_gateway" "main" {
  count         = var.single_nat_gateway ? 1 : var.az_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name        = "${var.environment}-nat-gw-${count.index}"
    Environment = var.environment
  }

  depends_on = [aws_internet_gateway.main]
}

# ---------------------------------------------------------------------------
# Private Subnets
# ---------------------------------------------------------------------------
resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + var.az_count)
  availability_zone = local.azs[count.index]

  tags = {
    Name                                           = "${var.environment}-private-${local.azs[count.index]}"
    Environment                                    = var.environment
    "kubernetes.io/role/internal-elb"               = "1"
    "kubernetes.io/cluster/${var.environment}-vycescore" = "shared"
  }
}

resource "aws_route_table" "private" {
  count  = var.az_count
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[var.single_nat_gateway ? 0 : count.index].id
  }

  tags = {
    Name        = "${var.environment}-private-rt-${count.index}"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# ---------------------------------------------------------------------------
# Database Subnets (isolated, no internet route)
# ---------------------------------------------------------------------------
resource "aws_subnet" "database" {
  count             = var.az_count
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + (2 * var.az_count))
  availability_zone = local.azs[count.index]

  tags = {
    Name        = "${var.environment}-database-${local.azs[count.index]}"
    Environment = var.environment
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.environment}-vycescore-db-subnet"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name        = "${var.environment}-vycescore-db-subnet"
    Environment = var.environment
  }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.environment}-vycescore-cache-subnet"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name        = "${var.environment}-vycescore-cache-subnet"
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# VPC Flow Logs
# ---------------------------------------------------------------------------
resource "aws_flow_log" "main" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  iam_role_arn         = aws_iam_role.flow_log.arn
  log_destination      = aws_cloudwatch_log_group.flow_log.arn
  max_aggregation_interval = 60

  tags = {
    Name        = "${var.environment}-vycescore-flow-log"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "flow_log" {
  name              = "/aws/vpc/flow-log/${var.environment}-vycescore"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role" "flow_log" {
  name = "${var.environment}-vycescore-flow-log-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "vpc-flow-logs.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "flow_log" {
  name = "${var.environment}-vycescore-flow-log-policy"
  role = aws_iam_role.flow_log.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Effect   = "Allow"
      Resource = "*"
    }]
  })
}
