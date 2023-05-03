(defproject jepsen.etcdemo "0.1.0-SNAPSHOT"
  :description "A Jepsen test for etcd"
  :license {:name "Eclipse Public License"
            :url "http://www.eclipse.org/legal/epl-v10.html"}
  :main jepsen.etcdemo
  :dependencies [[org.clojure/clojure "1.11.1"]
                 [jepsen "0.3.2-SNAPSHOT"]
                 [verschlimmbesserung "0.1.3"]])
