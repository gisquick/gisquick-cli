CREATE TABLE "app_user" (
	"username" varchar(150) PRIMARY KEY,
	"password" varchar(128) NOT NULL,
	"is_superuser" bool NOT NULL,
	"first_name" varchar(30) NOT NULL,
	"last_name" varchar(150) NOT NULL,
	"email" varchar(254) NOT NULL,
	"is_active" bool NOT NULL,
	"date_joined" timestamptz NULL,
	"last_login" timestamptz NULL
);