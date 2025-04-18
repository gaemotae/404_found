CREATE TABLE Community (
    post_id NUMBER PRIMARY KEY,
    user_id NUMBER NOT NULL,
    content CLOB NOT NULL,
    image_url VARCHAR2(500),
    likes_count NUMBER DEFAULT 0,
    created_at TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT fk_community_user FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- �ڵ� ���� SEQUENCE & TRIGGER
CREATE SEQUENCE community_seq START WITH 1 INCREMENT BY 1;
CREATE OR REPLACE TRIGGER community_trigger
BEFORE INSERT ON Community
FOR EACH ROW
BEGIN
    SELECT community_seq.NEXTVAL INTO :NEW.post_id FROM DUAL;
END;
/
