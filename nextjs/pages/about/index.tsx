import React from "react";
import HeaderEvaluator, { MenuItem } from "../../components/HeaderEvaluator";
import { UserCardImage } from "../../components/PersonCard";
import { Center, Group } from "@mantine/core";

const AboutPage = () => {
  return (
    <>
      <HeaderEvaluator activeTab={MenuItem.About} />
      <Center>
        <Group pt={100}>
          <UserCardImage
            avatar="data:image/jpeg;base64,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"
            name="M Dzakwan Falih"
            job="Infra Lead @ Fisclouds"
            twitterHandle="learningwithjek"
            githubHandle="dzakwanf"
          />
          <UserCardImage
            avatar="https://media.licdn.com/dms/image/D5603AQG8IWq7BboFQA/profile-displayphoto-shrink_800_800/0/1681920803609?e=2147483647&v=beta&t=Dl6C8kpSjviEUlExuwnJoVdu1wP6IlhMkNt-U3md6og"
            name="Ainul Yaqin"
            job="Data Lead  @ Fisclouds"
            twitterHandle="sfgunslinger"
            githubHandle="dankolesnikov"
          />
          <UserCardImage
            avatar="https://pbs.twimg.com/profile_images/1508934858990505986/-bPAFfFU_400x400.png"
            name="Ben"
            job="Software @ Rainbow"
            twitterHandle="thebengoldberg"
            githubHandle="benisgold"
          />
        </Group>
      </Center>
    </>
  );
};
export default AboutPage;
